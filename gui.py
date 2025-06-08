import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import yaml
import subprocess
import threading
import os
import sys
import logging
import json

# Import job search module
from job_search import JobSearchApp

CONFIG_PATH = 'config.yml'
MAIN_SCRIPT_PATH = 'main.py'
AI_PROMPT_SETTINGS_PATH = os.path.join('data', 'ai_prompt_settings.json')

# Modern color scheme
COLORS = {
    'primary': '#2563eb',      # Blue
    'primary_hover': '#1d4ed8', # Darker blue
    'secondary': '#64748b',     # Slate gray
    'accent': '#10b981',        # Green
    'accent_hover': '#059669',  # Darker green
    'background': '#f8fafc',    # Light gray background
    'surface': '#ffffff',       # White surface
    'surface_secondary': '#f1f5f9', # Light blue-gray
    'border': '#e2e8f0',        # Light border
    'text_primary': '#1e293b',  # Dark text
    'text_secondary': '#64748b', # Gray text
    'error': '#ef4444',         # Red
    'warning': '#f59e0b',       # Orange
    'success': '#10b981',       # Green
}

TOOLTIPS = {
    # Credentials
    'username': 'Your LinkedIn email address.',
    'password': 'Your LinkedIn password. Stored in config.yml.',
    # Search Profile (Primary)
    'query': 'Keywords for job search (e.g., \'Data Analyst\'). Blank if using auto features. Use comma-separated terms for sequence. Special keywords: \'recommended\', \'easy_apply\', \'easyapply\' (case-insensitive).',
    'location': 'Target location. \'United Kingdom\' or \'Sheffield\' auto-fills GeoID.',
    'geoId': 'LinkedIn GeoID. Auto-filled for UK/Sheffield.',
    'auto_easy': 'Use LinkedIn\'s \'Easy Apply\' collection (ignores query/filters).',
    'auto_recommend': 'Use LinkedIn\'s \'Recommended\' collection (ignores query/filters).',
    # Filters
    'distance_km': 'Search radius in kilometers.',
    'date_posted': 'Job posting recency.',
    'remote': 'Select preferred work arrangements.',
    'experience': 'Select desired experience levels.',
    'job_type': 'Select desired job types.',
    'low_number_applicants': 'Filter for jobs with <10 applicants.',
    # Runtime & Advanced
    'banned_words': 'Job titles with these words (one per line) are skipped.',
    'banned_companies': 'Company names (one per line) that will be skipped. Uses exact matching (case-insensitive).',
    'headless': 'Run browser invisibly (True) or visibly (False).',
    'accept_cookies_selector': 'CSS selector for cookie accept button.',
    'random_delay_ms': 'Min/Max delay (ms) between actions.',
    'max_tabs': 'Max simultaneous job tabs.',
    'log_level': 'Logging detail (DEBUG, INFO, WARNING, ERROR).',
    'proxy_pool': 'Proxies (one per line, user:pass@host:port or host:port). Optional.',
    'date_posted_custom_hours_value': 'Specify hours (1-23) for custom date posted filter. Value is used if "Custom Hours" is selected.',
    'ai_extra_information': 'Additional context for the AI when answering job application questions. This information will be injected into the prompt.'
}

LOCATION_GEOID_MAP = {
    "United Kingdom": 101165590,
    "Sheffield": 104470941
}

class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_win = None
        self.widget.bind("<Enter>", self.show, add='+')
        self.widget.bind("<Leave>", self.hide, add='+')

    def show(self, event=None):
        if self.tooltip_win or not self.text: return
        try:
            x, y, _, _ = self.widget.bbox("insert")
            x += self.widget.winfo_rootx() + 25
            y += self.widget.winfo_rooty() + 20
        except (TypeError, tk.TclError):
            # Fallback for widgets that don't support bbox("insert")
            x = self.widget.winfo_rootx() + 25
            y = self.widget.winfo_rooty() + 20
        
        self.tooltip_win = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        # Enhanced tooltip styling
        label = tk.Label(tw, text=self.text, justify='left', 
                         background="#2d3748", foreground="white",
                         relief='solid', borderwidth=0, wraplength=280,
                         font=("Segoe UI", 9), padx=12, pady=8)
        label.pack(ipadx=1)
        
        # Add subtle shadow effect
        tw.attributes('-topmost', True)

    def hide(self, event=None):
        if self.tooltip_win:
            self.tooltip_win.destroy()
        self.tooltip_win = None

class AppConfigurator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LinkedIn Bot Configurator")
        self.geometry("850x750")
        self.minsize(850, 750)
        
        # Set window icon and background
        self.configure(bg=COLORS['background'])
        
        # Try to set window icon (optional, will fail gracefully if no icon file)
        try:
            # You can add an icon file here if available
            pass
        except:
            pass

        self.config_data = self.load_config()
        self.ai_prompt_settings = self.load_ai_prompt_settings()
        self.vars = {}

        self.setup_styles()
        self.create_widgets()
        self.load_values_from_config()
        self.load_ai_values_to_gui()
        
        # Update banned display counts after loading
        if hasattr(self, 'banned_keywords_display'):
            self.update_banned_displays()

    def setup_styles(self):
        """Configure modern styling for all widgets"""
        style = ttk.Style(self)
        
        # Try to use a more modern theme if available
        try:
            style.theme_use('clam')
        except:
            style.theme_use('default')
        
        # Configure main styles
        style.configure('Modern.TFrame', 
                       background=COLORS['surface'],
                       relief='flat',
                       borderwidth=1)
        
        style.configure('Card.TLabelframe', 
                       background=COLORS['surface'],
                       relief='solid',
                       borderwidth=1,
                       labelmargins=(8, 4, 8, 4))
        
        style.configure('Card.TLabelframe.Label',
                       background=COLORS['surface'],
                       foreground=COLORS['text_primary'],
                       font=("Segoe UI", 9, "bold"))
        
        # Enhanced button styles with better visibility
        style.configure('Primary.TButton',
                       background=COLORS['primary'],
                       foreground='white',
                       font=("Segoe UI", 9, "bold"),
                       padding=(12, 8),
                       relief='raised',
                       borderwidth=2)
        
        style.map('Primary.TButton',
                 background=[('active', COLORS['primary_hover']),
                           ('pressed', COLORS['primary_hover']),
                           ('disabled', '#cccccc')])
        
        style.configure('Success.TButton',
                       background=COLORS['accent'],
                       foreground='white',
                       font=("Segoe UI", 9, "bold"),
                       padding=(12, 8),
                       relief='raised',
                       borderwidth=2)
        
        style.map('Success.TButton',
                 background=[('active', COLORS['accent_hover']),
                           ('pressed', COLORS['accent_hover']),
                           ('disabled', '#cccccc')])
        
        # Enhanced entry styles
        style.configure('Modern.TEntry',
                       fieldbackground=COLORS['surface'],
                       borderwidth=1,
                       relief='solid',
                       padding=(8, 4),
                       font=("Segoe UI", 9))
        
        style.map('Modern.TEntry',
                 focuscolor=[('!focus', COLORS['border'])],
                 bordercolor=[('focus', COLORS['primary'])])
        
        # Enhanced combobox styles
        style.configure('Modern.TCombobox',
                       fieldbackground=COLORS['surface'],
                       borderwidth=1,
                       relief='solid',
                       padding=(8, 4),
                       font=("Segoe UI", 9))
        
        # Enhanced checkbox styles
        style.configure('Modern.TCheckbutton',
                       background=COLORS['surface'],
                       foreground=COLORS['text_primary'],
                       font=("Segoe UI", 9),
                       padding=(4, 2))
        
        # Enhanced label styles
        style.configure('Header.TLabel',
                       background=COLORS['surface'],
                       foreground=COLORS['text_primary'],
                       font=("Segoe UI", 10, "bold"),
                       padding=(0, 4))
        
        style.configure('Body.TLabel',
                       background=COLORS['surface'],
                       foreground=COLORS['text_secondary'],
                       font=("Segoe UI", 9),
                       padding=(0, 2))
        
        style.configure('Info.TLabel',
                       background=COLORS['surface_secondary'],
                       foreground=COLORS['text_secondary'],
                       font=("Segoe UI", 8),
                       padding=(8, 4),
                       relief='solid',
                       borderwidth=1)
        
        # Notebook styling
        style.configure('Modern.TNotebook',
                       background=COLORS['background'],
                       borderwidth=0)
        
        style.configure('Modern.TNotebook.Tab',
                       background=COLORS['surface_secondary'],
                       foreground=COLORS['text_primary'],
                       font=("Segoe UI", 9, "bold"),
                       padding=(12, 6),
                       borderwidth=1)
        
        style.map('Modern.TNotebook.Tab',
                 background=[('selected', COLORS['surface']),
                           ('active', COLORS['border'])])

    def create_widgets(self):
        """Create the main widget layout with enhanced styling"""
        # Main container using grid for better control
        main_frame = ttk.Frame(self, style='Modern.TFrame', padding="10")
        main_frame.pack(expand=True, fill='both')
        
        # Configure grid weights
        main_frame.grid_rowconfigure(1, weight=1)  # Notebook expands
        main_frame.grid_columnconfigure(0, weight=1)
        
        # Compact title header
        title_frame = ttk.Frame(main_frame, style='Modern.TFrame')
        title_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        
        title_label = ttk.Label(title_frame, 
                               text="LinkedIn Bot Configurator",
                               font=("Segoe UI", 12, "bold"),
                               foreground=COLORS['primary'],
                               background=COLORS['surface'])
        title_label.pack(side=tk.LEFT)
        
        subtitle_label = ttk.Label(title_frame,
                                  text="Configure your automated job applications",
                                  font=("Segoe UI", 8),
                                  foreground=COLORS['text_secondary'],
                                  background=COLORS['surface'])
        subtitle_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Create notebook with fixed size
        notebook = ttk.Notebook(main_frame, style='Modern.TNotebook')
        notebook.grid(row=1, column=0, sticky='nsew', pady=(5, 10))

        self.create_core_tab(notebook)
        self.create_filters_tab(notebook)
        self.create_runtime_tab(notebook)
        self.create_ai_settings_tab(notebook)

        # Button frame - always visible at bottom
        button_frame = tk.Frame(main_frame, relief='solid', borderwidth=1, bg=COLORS['surface'])
        button_frame.grid(row=2, column=0, sticky='ew', pady=10)

        # Create buttons with explicit styling
        self.start_button = tk.Button(button_frame, 
                                     text="🚀 Save & Start Bot",
                                     command=self.start_bot,
                                     bg=COLORS['primary'],
                                     fg='white',
                                     font=("Segoe UI", 9, "bold"),
                                     padx=15, pady=8,
                                     relief='raised',
                                     borderwidth=2)
        self.start_button.pack(side=tk.LEFT, padx=(10, 15), pady=8)
        
        self.job_search_button = tk.Button(button_frame, 
                                          text="🔍 Job Search",
                                          command=self.open_job_search,
                                          bg=COLORS['accent'],
                                          fg='white',
                                          font=("Segoe UI", 9, "bold"),
                                          padx=15, pady=8,
                                          relief='raised',
                                          borderwidth=2)
        self.job_search_button.pack(side=tk.LEFT, padx=10, pady=8)
        
        print("✅ Buttons created successfully!")

    def add_tooltip(self, widget, key):
        if key in TOOLTIPS: Tooltip(widget, TOOLTIPS[key])

    def create_entry(self, parent, key, label_text, row, col, widget_kwargs=None, grid_kwargs=None):
        if widget_kwargs is None: widget_kwargs = {}
        if grid_kwargs is None: grid_kwargs = {}
        
        # Compact grid settings
        grid_params = {'row': row, 'column': col + 1, 'sticky': 'ew', 'padx': (5, 8), 'pady': 3}
        grid_params.update(grid_kwargs)
        
        # Enhanced label styling
        label = ttk.Label(parent, text=label_text, style='Body.TLabel')
        label.grid(row=row, column=col, sticky='w', padx=(8, 5), pady=3)
        
        # Ensure textvariable is passed correctly if provided
        if 'textvariable' not in widget_kwargs:
             self.vars[key] = tk.StringVar()
             widget_kwargs['textvariable'] = self.vars[key]
        elif key not in self.vars:
             self.vars[key] = widget_kwargs['textvariable']
             
        # Add modern styling to entry
        if 'style' not in widget_kwargs:
            widget_kwargs['style'] = 'Modern.TEntry'
            
        entry = ttk.Entry(parent, **widget_kwargs)
        entry.grid(**grid_params)
        self.add_tooltip(entry, key)
        return entry

    def create_checkbox(self, parent, key, label_text, row, col, widget_kwargs=None, grid_kwargs=None):
        if widget_kwargs is None: widget_kwargs = {}
        if grid_kwargs is None: grid_kwargs = {}

        # Compact grid settings
        grid_params = {'row': row, 'column': col, 'sticky': 'w', 'padx': 8, 'pady': 3}
        grid_params.update(grid_kwargs)
        
        self.vars[key] = tk.BooleanVar()
        
        # Add modern styling to checkbox
        if 'style' not in widget_kwargs:
            widget_kwargs['style'] = 'Modern.TCheckbutton'
            
        cb = ttk.Checkbutton(parent, text=label_text, variable=self.vars[key], **widget_kwargs)
        cb.grid(**grid_params)
        self.add_tooltip(cb, key)
        return cb

    def create_combobox(self, parent, key, label_text, values, row, col, widget_kwargs=None, grid_kwargs=None):
        if widget_kwargs is None: widget_kwargs = {}
        if grid_kwargs is None: grid_kwargs = {}
        
        grid_params = {'row': row, 'column': col + 1, 'sticky': 'ew', 'padx': (5, 8), 'pady': 3}
        grid_params.update(grid_kwargs)

        # Ensure 'state' defaults to 'readonly' if not provided
        if 'state' not in widget_kwargs:
            widget_kwargs['state'] = 'readonly'
            
        # Add modern styling
        if 'style' not in widget_kwargs:
            widget_kwargs['style'] = 'Modern.TCombobox'
            
        # Ensure textvariable is passed correctly if provided
        if 'textvariable' not in widget_kwargs:
            self.vars[key] = tk.StringVar()
            widget_kwargs['textvariable'] = self.vars[key]
        elif key not in self.vars:
             self.vars[key] = widget_kwargs['textvariable']

        label = ttk.Label(parent, text=label_text, style='Body.TLabel')
        label.grid(row=row, column=col, sticky='w', padx=(8, 5), pady=3)
        
        combo = ttk.Combobox(parent, values=values, **widget_kwargs)
        combo.grid(**grid_params)
        self.add_tooltip(combo, key)
        return combo

    def create_scrolledtext(self, parent, key, height=4, width=35):
        # Compact ScrolledText with modern styling
        st = scrolledtext.ScrolledText(parent, wrap=tk.WORD, height=height, width=width,
                                      font=("Consolas", 9),
                                      bg=COLORS['surface'],
                                      fg=COLORS['text_primary'],
                                      selectbackground=COLORS['primary'],
                                      selectforeground='white',
                                      relief='solid',
                                      borderwidth=1,
                                      padx=8,
                                      pady=6)
        st.grid(row=0, column=0, sticky='nsew', padx=8, pady=8)
        self.add_tooltip(st, key)
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        self.vars[key] = st
        return st

    def create_core_tab(self, parent):
        tab = ttk.Frame(parent, style='Modern.TFrame', padding=10)
        parent.add(tab, text='🔐 Core Settings')

        # Compact credentials section
        cred_frame = ttk.LabelFrame(tab, text="Credentials", style='Card.TLabelframe', padding=10)
        cred_frame.pack(fill='x', pady=(0, 8))
        
        self.create_entry(cred_frame, 'username', "Email:", 0, 0, widget_kwargs={'width': 35})
        self.create_entry(cred_frame, 'password', "Password:", 1, 0, widget_kwargs={'width': 35, 'show': '*'}) 
        cred_frame.columnconfigure(1, weight=1)

        # Compact search profile section
        search_frame = ttk.LabelFrame(tab, text="Search Profile", style='Card.TLabelframe', padding=10)
        search_frame.pack(fill='x', pady=(0, 8))
        
        self.create_entry(search_frame, 'query', "Search Keywords:", 0, 0, 
                        widget_kwargs={'width': 55}, 
                        grid_kwargs={'columnspan': 3}) 

        # Enhanced info section with modern styling
        info_frame = ttk.Frame(search_frame, style='Modern.TFrame', padding=15)
        info_frame.grid(row=1, column=0, columnspan=4, sticky='ew', pady=15)
        info_frame.configure(relief='solid', borderwidth=1)
        
        info_text = ("💡 Pro Tip: Use comma-separated keywords for sequence searching\n"
                    "   Example: 'software,consultant,recommended' searches each term in order\n"
                    "   Special keywords: 'recommended', 'easy_apply', 'easyapply' (case-insensitive)")
        info_label = ttk.Label(info_frame, text=info_text, style='Info.TLabel')
        info_label.pack(fill='x')

        # Location section with enhanced styling
        ttk.Label(search_frame, text="Location:", style='Body.TLabel').grid(row=2, column=0, sticky='w', padx=(15, 10), pady=8)
        self.vars['location'] = tk.StringVar()
        locations = list(LOCATION_GEOID_MAP.keys()) + ["Other (Manual GeoID)"]
        location_combo = ttk.Combobox(search_frame, textvariable=self.vars['location'], 
                                     values=locations, width=30, style='Modern.TCombobox')
        location_combo.grid(row=2, column=1, sticky='ew', padx=(10, 15), pady=8)
        location_combo.bind('<<ComboboxSelected>>', self.update_geoId)
        location_combo.bind('<KeyRelease>', self.update_geoId)
        self.add_tooltip(location_combo, 'location')

        # GeoID Entry
        ttk.Label(search_frame, text="GeoID:", style='Body.TLabel').grid(row=2, column=2, sticky='w', padx=(15, 10), pady=8)
        self.vars['geoId'] = tk.StringVar()
        self.geoId_entry = ttk.Entry(search_frame, textvariable=self.vars['geoId'], 
                                    width=20, style='Modern.TEntry')
        self.geoId_entry.grid(row=2, column=3, sticky='ew', padx=(10, 15), pady=8)
        self.add_tooltip(self.geoId_entry, 'geoId')

        # Enhanced auto options
        auto_frame = ttk.Frame(search_frame, style='Modern.TFrame', padding=15)
        auto_frame.grid(row=3, column=0, columnspan=4, sticky='ew', pady=15)
        
        self.vars['auto_easy'] = tk.BooleanVar()
        cb_easy = ttk.Checkbutton(auto_frame, text="📋 Use Easy Apply List", 
                                 variable=self.vars['auto_easy'], style='Modern.TCheckbutton')
        cb_easy.pack(side=tk.LEFT, padx=(0, 20))
        self.add_tooltip(cb_easy, 'auto_easy')

        self.vars['auto_recommend'] = tk.BooleanVar()
        cb_rec = ttk.Checkbutton(auto_frame, text="⭐ Use Recommended List", 
                                variable=self.vars['auto_recommend'], style='Modern.TCheckbutton')
        cb_rec.pack(side=tk.LEFT)
        self.add_tooltip(cb_rec, 'auto_recommend')

        search_frame.columnconfigure(1, weight=1)
        search_frame.columnconfigure(3, weight=1)

    def create_filters_tab(self, parent):
        tab = ttk.Frame(parent, style='Modern.TFrame', padding=20)
        parent.add(tab, text='🔍 Search Filters')

        filter_frame = ttk.LabelFrame(tab, text="Job Filters", style='Card.TLabelframe', padding=20)
        filter_frame.pack(fill='both', expand=True)

        basic_frame = ttk.Frame(filter_frame, style='Modern.TFrame')
        basic_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 20))
        multi_frame = ttk.Frame(filter_frame, style='Modern.TFrame')
        multi_frame.grid(row=0, column=1, sticky='nsew')
        filter_frame.columnconfigure(0, weight=1)
        filter_frame.columnconfigure(1, weight=1)

        # Basic Filters with enhanced styling
        self.vars['distance_km'] = tk.IntVar()
        self.create_combobox(basic_frame, 'distance_km', "🗺️ Distance (km):", [8, 15, 40, 80], 0, 0, 
                             widget_kwargs={'width': 12, 'textvariable': self.vars['distance_km']}) 
        
        self.vars['date_posted'] = tk.StringVar()
        date_options = ['Any Time', 'Past 24 hours', 'Past Week', 'Past Month', 'Custom Hours']
        date_posted_combo = self.create_combobox(basic_frame, 'date_posted', "📅 Date Posted:", date_options, 1, 0, 
                                               widget_kwargs={'textvariable': self.vars['date_posted']})
        date_posted_combo.bind('<<ComboboxSelected>>', self.on_date_posted_selected)

        # Enhanced custom hours slider
        self.date_posted_custom_hours_label = ttk.Label(basic_frame, text="⏰ Custom Hours (1-23):", style='Body.TLabel')
        self.vars['date_posted_custom_hours_value'] = tk.IntVar(value=12)
        self.date_posted_custom_hours_slider = ttk.Scale(
            basic_frame, 
            from_=1, 
            to=23, 
            orient=tk.HORIZONTAL, 
            variable=self.vars['date_posted_custom_hours_value'],
            length=200,
            command=self.update_custom_hours_indicator
        )
        self.add_tooltip(self.date_posted_custom_hours_slider, 'date_posted_custom_hours_value')
        self.custom_hours_value_label = ttk.Label(basic_frame, text="12h", style='Body.TLabel')

        self.create_checkbox(basic_frame, 'low_number_applicants', "🎯 Low Number Applicants Filter", 2, 0, grid_kwargs={'columnspan': 2})
        basic_frame.columnconfigure(1, weight=1)

        # Multi-Select Filters with enhanced styling
        self.vars['remote'] = self._create_multi_check(multi_frame, 'remote', "🏠 Remote Options", ["on_site", "remote", "hybrid"])
        self.vars['experience'] = self._create_multi_check(multi_frame, 'experience', "💼 Experience Levels", ["internship", "entry_level", "associate", "mid_senior_level", "director", "executive"], cols=2)
        self.vars['job_type'] = self._create_multi_check(multi_frame, 'job_type', "⏱️ Job Types", ["full_time", "part_time", "contract", "temporary", "volunteer", "internship"], cols=2)

    def on_date_posted_selected(self, event=None):
        # Show/hide custom hours slider based on selection
        is_custom = self.vars['date_posted'].get() == 'Custom Hours'
        
        if is_custom:
            self.date_posted_custom_hours_label.grid(row=3, column=0, sticky='w', padx=(15, 10), pady=8)
            self.date_posted_custom_hours_slider.grid(row=3, column=1, sticky='ew', padx=(10, 15), pady=8)
            self.custom_hours_value_label.grid(row=3, column=2, sticky='w', padx=(10, 15), pady=8)
            self.update_custom_hours_indicator(self.vars['date_posted_custom_hours_value'].get())
        else:
            self.date_posted_custom_hours_label.grid_remove()
            self.date_posted_custom_hours_slider.grid_remove()
            self.custom_hours_value_label.grid_remove()

    def _create_multi_check(self, parent, key, label_text, options, cols=3):
        frame = ttk.LabelFrame(parent, text=label_text, style='Card.TLabelframe', padding=15)
        frame.pack(fill='x', pady=(0, 15))
        self.add_tooltip(frame, key)
        vars_dict = {}
        for i, option in enumerate(options):
            var = tk.BooleanVar()
            cb = ttk.Checkbutton(frame, text=option.replace('_', ' ').title(), 
                               variable=var, style='Modern.TCheckbutton')
            cb.grid(row=i // cols, column=i % cols, sticky='w', padx=10, pady=4)
            vars_dict[option] = var
        return vars_dict

    def create_runtime_tab(self, parent):
        tab = ttk.Frame(parent, style='Modern.TFrame', padding=20)
        parent.add(tab, text='⚙️ Runtime & Advanced')
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=0, minsize=80)  # Fixed height for banned keywords
        tab.rowconfigure(2, weight=0, minsize=80)  # Fixed height for banned companies
        tab.rowconfigure(3, weight=1)  # Proxy section can expand

        runtime_frame = ttk.LabelFrame(tab, text="Runtime Settings", style='Card.TLabelframe', padding=20)
        runtime_frame.grid(row=0, column=0, sticky='ew', pady=(0, 20))

        self.create_checkbox(runtime_frame, 'headless', "👻 Run Headless (Invisible Browser)", 0, 0, grid_kwargs={'columnspan': 2})
        self.create_entry(runtime_frame, 'accept_cookies_selector', "🍪 Cookie Selector:", 1, 0, widget_kwargs={'width': 30})
        
        # Enhanced delay frame
        delay_frame = ttk.Frame(runtime_frame, style='Modern.TFrame', padding=10)
        delay_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=10)
        delay_frame.configure(relief='solid', borderwidth=1)
        
        ttk.Label(delay_frame, text="⏱️ Random Delay (ms):", style='Body.TLabel').pack(side=tk.LEFT, padx=(0, 10))
        self.vars['random_delay_ms_min'] = tk.IntVar()
        min_entry = ttk.Entry(delay_frame, textvariable=self.vars['random_delay_ms_min'], 
                             width=8, style='Modern.TEntry')
        min_entry.pack(side=tk.LEFT, padx=5)
        self.add_tooltip(min_entry, 'random_delay_ms')
        
        ttk.Label(delay_frame, text="to", style='Body.TLabel').pack(side=tk.LEFT, padx=5)
        
        self.vars['random_delay_ms_max'] = tk.IntVar()
        max_entry = ttk.Entry(delay_frame, textvariable=self.vars['random_delay_ms_max'], 
                             width=8, style='Modern.TEntry')
        max_entry.pack(side=tk.LEFT, padx=5)
        self.add_tooltip(max_entry, 'random_delay_ms')

        self.vars['max_tabs'] = tk.IntVar()
        self.create_entry(runtime_frame, 'max_tabs', "📑 Max Job Tabs:", 3, 0, 
                          widget_kwargs={'width': 8, 'textvariable': self.vars['max_tabs']})
        
        self.create_combobox(runtime_frame, 'log_level', "📝 Log Level:", ["DEBUG", "INFO", "WARNING", "ERROR"], 4, 0, 
                             widget_kwargs={'width': 12})
        runtime_frame.columnconfigure(1, weight=1)

        # Banned Keywords - Enhanced layout with proper sizing
        banned_frame = tk.LabelFrame(tab, text="🚫 Banned Keywords", 
                                    bg='white', fg='black', font=("Segoe UI", 10, "bold"),
                                    relief='solid', borderwidth=2, padx=15, pady=15)
        banned_frame.grid(row=1, column=0, sticky='ew', pady=(0, 20), padx=5, ipady=10)
        banned_frame.columnconfigure(0, weight=1)
        
        # Create hidden scrolledtext for compatibility
        self.vars['banned_words'] = scrolledtext.ScrolledText(tab, height=1, width=1)
        self.vars['banned_words'].pack_forget()
        
        # Enhanced horizontal layout with grid for better control
        self.banned_keywords_display = tk.Entry(banned_frame, width=40, font=("Segoe UI", 11),
                                               relief='solid', borderwidth=2, bg='#f8fafc', 
                                               state='readonly')
        self.banned_keywords_display.grid(row=0, column=0, sticky='ew', padx=(0, 15), pady=8)
        self.banned_keywords_display.insert(0, "No keywords")
        
        self.banned_keywords_btn = tk.Button(banned_frame, text="✏️ Edit Keywords", 
                                           command=self.open_banned_keywords_editor,
                                           bg='#10b981', fg='white', font=("Segoe UI", 10, "bold"),
                                           relief='raised', borderwidth=2, padx=25, pady=10,
                                           width=15)
        self.banned_keywords_btn.grid(row=0, column=1, pady=8)
        print("✅ Created banned keywords button")

        # Banned Companies - Enhanced layout with proper sizing
        banned_companies_frame = tk.LabelFrame(tab, text="🏢 Banned Companies",
                                              bg='white', fg='black', font=("Segoe UI", 10, "bold"), 
                                              relief='solid', borderwidth=2, padx=15, pady=15)
        banned_companies_frame.grid(row=2, column=0, sticky='ew', pady=(0, 20), padx=5, ipady=10)
        banned_companies_frame.columnconfigure(0, weight=1)
        
        # Create hidden scrolledtext for compatibility
        self.vars['banned_companies'] = scrolledtext.ScrolledText(tab, height=1, width=1) 
        self.vars['banned_companies'].pack_forget()
        
        # Enhanced horizontal layout with grid for better control
        self.banned_companies_display = tk.Entry(banned_companies_frame, width=40, font=("Segoe UI", 11),
                                                relief='solid', borderwidth=2, bg='#f8fafc',
                                                state='readonly')
        self.banned_companies_display.grid(row=0, column=0, sticky='ew', padx=(0, 15), pady=8)
        self.banned_companies_display.insert(0, "No companies")
        
        self.banned_companies_btn = tk.Button(banned_companies_frame, text="✏️ Edit Companies", 
                                             command=self.open_banned_companies_editor,
                                             bg='#10b981', fg='white', font=("Segoe UI", 10, "bold"),
                                             relief='raised', borderwidth=2, padx=25, pady=10,
                                             width=15)
        self.banned_companies_btn.grid(row=0, column=1, pady=8)
        print("✅ Created banned companies button")

        proxy_frame = ttk.LabelFrame(tab, text="🌐 Proxy Pool (Optional)", style='Card.TLabelframe', padding=15)
        proxy_frame.grid(row=3, column=0, sticky='nsew')
        self.create_scrolledtext(proxy_frame, 'proxy_pool', height=4)

    def create_ai_settings_tab(self, parent):
        tab = ttk.Frame(parent, style='Modern.TFrame', padding=20)
        parent.add(tab, text='🤖 AI Settings')

        ai_prompt_frame = ttk.LabelFrame(tab, text="AI Prompt Configuration", style='Card.TLabelframe', padding=20)
        ai_prompt_frame.pack(fill='both', expand=True)

        # Enhanced header
        header_label = ttk.Label(ai_prompt_frame, 
                                text="🎯 Extra Information for AI Prompts:",
                                style='Header.TLabel')
        header_label.grid(row=0, column=0, sticky='w', pady=(0, 15))
        
        # Info section
        info_frame = ttk.Frame(ai_prompt_frame, style='Modern.TFrame', padding=15)
        info_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(0, 15))
        info_frame.configure(relief='solid', borderwidth=1)
        
        info_text = ("💡 This information will be provided to the AI when answering job application questions.\n"
                    "   Include details about your background, experience, preferences, and any other context\n"
                    "   that will help the AI provide more personalized and accurate responses.")
        info_label = ttk.Label(info_frame, text=info_text, style='Info.TLabel')
        info_label.pack(fill='x')
        
        # Text area with enhanced styling
        st_frame = ttk.Frame(ai_prompt_frame, style='Modern.TFrame')
        st_frame.grid(row=2, column=0, columnspan=2, sticky='nsew', pady=(0, 20))
        st_frame.rowconfigure(0, weight=1)
        st_frame.columnconfigure(0, weight=1)
        
        self.ai_extra_info_text = self.create_scrolledtext(st_frame, 'ai_extra_information', height=12, width=75)

        # Enhanced save button
        save_ai_button = ttk.Button(ai_prompt_frame, 
                                   text="💾 Save AI Prompt Settings", 
                                   command=self.save_ai_prompt_settings_from_gui,
                                   style='Success.TButton')
        save_ai_button.grid(row=3, column=0, columnspan=2, pady=15)

        ai_prompt_frame.columnconfigure(0, weight=1)
        ai_prompt_frame.rowconfigure(2, weight=1)

    def update_geoId(self, event=None):
        loc = self.vars['location'].get()
        if loc in LOCATION_GEOID_MAP:
            self.vars['geoId'].set(LOCATION_GEOID_MAP[loc])
            self.geoId_entry.config(state='readonly')
        else:
            if self.geoId_entry.cget('state') == 'readonly':
                self.vars['geoId'].set("")
            self.geoId_entry.config(state='normal')

    def load_config(self):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            return {}
        except yaml.YAMLError as e:
            messagebox.showerror("Config Error", f"Error loading {CONFIG_PATH}: {e}")
            return {}

    def load_ai_prompt_settings(self):
        try:
            if not os.path.exists(AI_PROMPT_SETTINGS_PATH):
                # Create the directory if it doesn't exist
                os.makedirs(os.path.dirname(AI_PROMPT_SETTINGS_PATH), exist_ok=True)
                # Create a default file if it doesn't exist
                default_content = {"extra_information": "Extra information user is Male, age 23, has BSc physics, living in Sheffield, England, United Kingdom, for years of experience quesitons use heuristics and CV information if not default to 2. For more generic questions like why do you want the role answer appropriately proffessionally using the CV and job description in full \n"}
                with open(AI_PROMPT_SETTINGS_PATH, 'w', encoding='utf-8') as f:
                    json.dump(default_content, f, indent=4)
                return default_content
            
            with open(AI_PROMPT_SETTINGS_PATH, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                # Ensure 'extra_information' key exists, provide default if not
                if "extra_information" not in settings:
                    settings["extra_information"] = "Extra information user is Male, age 23, has BSc physics, living in Sheffield, England, United Kingdom, for years of experience quesitons use heuristics and CV information if not default to 2. For more generic questions like why do you want the role answer appropriately proffessionally using the CV and job description in full \n"
                return settings
        except FileNotFoundError:
            messagebox.showinfo("AI Settings Info", f"{AI_PROMPT_SETTINGS_PATH} not found. Creating with default AI prompt settings.")
            default_settings = {"extra_information": "Extra information user is Male, age 23, has BSc physics, living in Sheffield, England, United Kingdom, for years of experience quesitons use heuristics and CV information if not default to 2. For more generic questions like why do you want the role answer appropriately proffessionally using the CV and job description in full \n"}
            try:
                os.makedirs(os.path.dirname(AI_PROMPT_SETTINGS_PATH), exist_ok=True)
                with open(AI_PROMPT_SETTINGS_PATH, 'w', encoding='utf-8') as f:
                    json.dump(default_settings, f, indent=4)
            except Exception as e_save:
                messagebox.showerror("AI Settings Error", f"Could not create default AI settings file: {e_save}")
            return default_settings
        except json.JSONDecodeError as e:
            messagebox.showerror("AI Settings Error", f"Error decoding {AI_PROMPT_SETTINGS_PATH}: {e}. Using default settings.")
            return {"extra_information": "Extra information user is Male, age 23, has BSc physics, living in Sheffield, England, United Kingdom, for years of experience quesitons use heuristics and CV information if not default to 2. For more generic questions like why do you want the role answer appropriately proffessionally using the CV and job description in full \n"}
        except Exception as e:
            messagebox.showerror("AI Settings Error", f"An unexpected error occurred while loading {AI_PROMPT_SETTINGS_PATH}: {e}. Using default settings.")
            return {"extra_information": "Extra information user is Male, age 23, has BSc physics, living in Sheffield, England, United Kingdom, for years of experience quesitons use heuristics and CV information if not default to 2. For more generic questions like why do you want the role answer appropriately proffessionally using the CV and job description in full \n"}

    def load_values_from_config(self):
        if self.config_data is None: return
        cfg = self.config_data

        # Credentials
        self.vars['username'].set(cfg.get('credentials', {}).get('username', ''))
        self.vars['password'].set(cfg.get('credentials', {}).get('password', ''))

        # Search Profile (first one)
        profile = cfg.get('search_profiles', [{}])[0]
        self.vars['query'].set(profile.get('query', ''))
        loc = profile.get('location', '')
        self.vars['location'].set(loc if loc in LOCATION_GEOID_MAP or not loc else 'Other (Manual GeoID)')
        self.update_geoId()
        if loc not in LOCATION_GEOID_MAP:
             self.vars['geoId'].set(profile.get('geoId', ''))

        filters = profile.get('filters', {})
        self.vars['distance_km'].set(filters.get('distance_km', 15))
        date_posted_val = filters.get('date_posted', 'Any Time')
        if date_posted_val == 'custom_hours':
            self.vars['date_posted'].set('Custom Hours')
            custom_hours = filters.get('date_posted_custom_hours_value', 12)
            self.vars['date_posted_custom_hours_value'].set(custom_hours)
            self.update_custom_hours_indicator(custom_hours)
        else:
            self.vars['date_posted'].set(date_posted_val)
            self.vars['date_posted_custom_hours_value'].set(12)
            self.update_custom_hours_indicator(12)

        # Ensure slider visibility is updated after loading
        self.on_date_posted_selected() 

        self.vars['low_number_applicants'].set(filters.get('low_number_applicants', False))
        self.vars['auto_easy'].set(filters.get('auto_easy', False))
        self.vars['auto_recommend'].set(filters.get('auto_recommend', False))

        for key, var_dict in [('remote', self.vars['remote']), ('experience', self.vars['experience']), ('job_type', self.vars['job_type'])]:
            selected = filters.get(key, [])
            if isinstance(selected, list):
                for option, var in var_dict.items():
                    var.set(option in selected)

        # Runtime
        runtime = cfg.get('runtime', {})
        self.vars['headless'].set(runtime.get('headless', False))
        self.vars['accept_cookies_selector'].set(runtime.get('accept_cookies_selector', ''))
        delay = runtime.get('random_delay_ms', [800, 2200])
        self.vars['random_delay_ms_min'].set(delay[0] if isinstance(delay, list) and len(delay)>0 else 800)
        self.vars['random_delay_ms_max'].set(delay[1] if isinstance(delay, list) and len(delay)>1 else 2200)
        self.vars['max_tabs'].set(runtime.get('max_tabs', 1))
        self.vars['log_level'].set(runtime.get('log_level', 'INFO'))

        # Banned Words, Banned Companies & Proxy Pool
        for key in ['banned_words', 'banned_companies', 'proxy_pool']:
            if key == 'banned_words':
                data_list = cfg.get(key, [])
            elif key == 'banned_companies':
                data_list = cfg.get(key, [])
            elif key == 'proxy_pool':
                data_list = cfg.get('runtime', {}).get(key, [])
            else:
                data_list = []

            if not isinstance(data_list, list): data_list = []
            widget = self.vars[key]
            widget.delete('1.0', tk.END)
            widget.insert('1.0', '\n'.join(data_list))
        
        # Update the display entries after loading
        if hasattr(self, 'banned_keywords_display'):
            self.update_banned_displays()

    def load_ai_values_to_gui(self):
        """Loads AI prompt settings into the GUI."""
        if hasattr(self, 'ai_extra_info_text') and self.ai_extra_info_text:
            current_content = self.ai_prompt_settings.get('extra_information', "")
            self.ai_extra_info_text.delete('1.0', tk.END)
            self.ai_extra_info_text.insert('1.0', current_content)
        else:
            logging.warning("ai_extra_info_text widget not found when trying to load AI values.")

    def save_config(self):
        if self.config_data is None: return False
        cfg = self.config_data

        # Credentials
        if 'credentials' not in cfg: cfg['credentials'] = {}
        cfg['credentials']['username'] = self.vars['username'].get()
        cfg['credentials']['password'] = self.vars['password'].get()

        # Search Profile (update first)
        if 'search_profiles' not in cfg or not cfg['search_profiles']:
             cfg['search_profiles'] = [{}]
        profile = cfg['search_profiles'][0]
        profile['query'] = self.vars['query'].get()
        loc = self.vars['location'].get()
        profile['location'] = loc if loc != 'Other (Manual GeoID)' else ''
        profile['geoId'] = int(self.vars['geoId'].get()) if self.vars['geoId'].get().isdigit() else self.vars['geoId'].get()

        if 'filters' not in profile: profile['filters'] = {}
        filters = profile['filters']
        filters['distance_km'] = self.vars['distance_km'].get()
        
        # Save date_posted and custom hours
        date_posted_selection = self.vars['date_posted'].get()
        if date_posted_selection == 'Custom Hours':
            filters['date_posted'] = 'custom_hours'
            filters['date_posted_custom_hours_value'] = self.vars['date_posted_custom_hours_value'].get()
        else:
            filters['date_posted'] = date_posted_selection 
            if 'date_posted_custom_hours_value' in filters:
                del filters['date_posted_custom_hours_value']

        filters['low_number_applicants'] = self.vars['low_number_applicants'].get()
        filters['auto_easy'] = self.vars['auto_easy'].get()
        filters['auto_recommend'] = self.vars['auto_recommend'].get()

        for key, var_dict in [('remote', self.vars['remote']), ('experience', self.vars['experience']), ('job_type', self.vars['job_type'])]:
            filters[key] = [option for option, var in var_dict.items() if var.get()]

        # Runtime
        if 'runtime' not in cfg: cfg['runtime'] = {}
        runtime = cfg['runtime']
        runtime['headless'] = self.vars['headless'].get()
        runtime['accept_cookies_selector'] = self.vars['accept_cookies_selector'].get()
        runtime['random_delay_ms'] = [self.vars['random_delay_ms_min'].get(), self.vars['random_delay_ms_max'].get()]
        runtime['max_tabs'] = self.vars['max_tabs'].get()
        runtime['log_level'] = self.vars['log_level'].get()

        # Banned Words, Banned Companies & Proxy Pool
        for key in ['banned_words', 'banned_companies', 'proxy_pool']:
            widget = self.vars[key]
            data = widget.get('1.0', tk.END).strip().split('\n')
            data = [line for line in data if line]
            if key == 'banned_words':
                cfg[key] = data
            elif key == 'banned_companies':
                cfg[key] = data
            else:
                 runtime[key] = data

        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
            return True
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save {CONFIG_PATH}:\n{e}")
            return False

    def save_ai_prompt_settings_from_gui(self):
        """Saves AI prompt settings from the GUI to the JSON file."""
        if hasattr(self, 'ai_extra_info_text') and self.ai_extra_info_text:
            current_extra_info = self.vars['ai_extra_information'].get("1.0", tk.END).strip()
            
            self.ai_prompt_settings['extra_information'] = current_extra_info
            
            try:
                os.makedirs(os.path.dirname(AI_PROMPT_SETTINGS_PATH), exist_ok=True)
                with open(AI_PROMPT_SETTINGS_PATH, 'w', encoding='utf-8') as f:
                    json.dump(self.ai_prompt_settings, f, indent=4)
                
                # Enhanced success message with modern styling
                success_window = tk.Toplevel(self)
                success_window.title("Success")
                success_window.geometry("300x120")
                success_window.configure(bg=COLORS['surface'])
                success_window.resizable(False, False)
                success_window.transient(self)
                success_window.grab_set()
                
                # Center the window
                success_window.update_idletasks()
                x = (success_window.winfo_screenwidth() // 2) - (300 // 2)
                y = (success_window.winfo_screenheight() // 2) - (120 // 2)
                success_window.geometry(f"300x120+{x}+{y}")
                
                # Success message with icon
                message_frame = ttk.Frame(success_window, style='Modern.TFrame', padding=20)
                message_frame.pack(fill='both', expand=True)
                
                success_label = ttk.Label(message_frame, 
                                        text="✅ AI Prompt settings saved successfully!",
                                        font=("Segoe UI", 11),
                                        foreground=COLORS['success'],
                                        background=COLORS['surface'])
                success_label.pack(pady=(10, 20))
                
                close_button = ttk.Button(message_frame, 
                                        text="OK", 
                                        command=success_window.destroy,
                                        style='Success.TButton')
                close_button.pack()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save AI prompt settings: {e}")
        else:
            messagebox.showerror("Error", "AI extra information text area not found. Cannot save.")

    def run_main_script(self):
        try:
            python_executable = sys.executable
            process = subprocess.Popen([python_executable, MAIN_SCRIPT_PATH], 
                                       stdout=subprocess.PIPE, 
                                       stderr=subprocess.PIPE,
                                       text=True, 
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

            print(f"Starting {MAIN_SCRIPT_PATH}...")
            stdout, stderr = process.communicate()
            print(f"{MAIN_SCRIPT_PATH} finished.")
            if stdout:
                print("Output:\n", stdout)
            if stderr:
                print("Errors:\n", stderr, file=sys.stderr)
            
            # Enhanced completion notification
            self.start_button.config(state=tk.NORMAL, text="🚀 Save Config & Start Bot") 

        except FileNotFoundError:
            messagebox.showerror("Error", f"{MAIN_SCRIPT_PATH} not found.")
            self.start_button.config(state=tk.NORMAL, text="🚀 Save Config & Start Bot")
        except Exception as e:
            messagebox.showerror("Execution Error", f"Error running {MAIN_SCRIPT_PATH}:\n{e}")
            self.start_button.config(state=tk.NORMAL, text="🚀 Save Config & Start Bot")
        finally:
             if hasattr(self, 'start_button') and self.start_button.winfo_exists():
                self.start_button.config(state=tk.NORMAL, text="🚀 Save Config & Start Bot") 

    def start_bot(self):
        if not self.save_config():
            return

        # Enhanced button feedback
        self.start_button.config(state=tk.DISABLED, text="🔄 Bot Running...")
        
        # Run main.py in a separate thread to avoid blocking the GUI
        thread = threading.Thread(target=self.run_main_script, daemon=True)
        thread.start()

    def update_custom_hours_indicator(self, value):
        # Callback for the slider to update the indicator label
        try:
            val_int = int(float(value))
            self.custom_hours_value_label.config(text=f"{val_int}h")
        except ValueError:
            self.custom_hours_value_label.config(text="--h")
    
    def open_job_search(self):
        """Open the job search window"""
        try:
            job_search_window = JobSearchApp(self)
            job_search_window.focus_set()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open job search: {str(e)}")

    def open_banned_keywords_editor(self):
        """Opens popup editor for banned keywords"""
        print("✅ Opening banned keywords editor...")
        self._open_text_editor("🚫 Banned Keywords Editor", 
                              self.vars['banned_words'], 
                              self.banned_keywords_display,
                              "Enter banned keywords (one per line):")

    def open_banned_companies_editor(self):
        """Opens popup editor for banned companies"""
        print("✅ Opening banned companies editor...")
        self._open_text_editor("🏢 Banned Companies Editor", 
                              self.vars['banned_companies'], 
                              self.banned_companies_display,
                              "Enter banned companies (one per line):")

    def _open_text_editor(self, title, text_widget, display_widget, instruction):
        """Generic popup text editor"""
        # Create and configure the popup window
        editor = tk.Toplevel(self)
        editor.title(title)
        editor.geometry("650x500")  # Made larger to ensure buttons are visible
        editor.configure(bg='white')
        editor.resizable(True, True)  # Allow resizing
        
        # Make it modal
        editor.transient(self)
        editor.grab_set()
        
        # Main frame with padding - now using grid
        main_frame = tk.Frame(editor, bg='white')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Configure grid layout for the main frame
        main_frame.rowconfigure(1, weight=1)  # Text area row should expand
        main_frame.columnconfigure(0, weight=1) # The single column should expand

        # Instruction label
        instruction_label = tk.Label(main_frame, text=instruction, 
                                     font=("Segoe UI", 12, "bold"),
                                     bg='white', fg='black')
        instruction_label.grid(row=0, column=0, sticky='w', pady=(0, 15))
        
        # Text area with scrollbar
        text_area = scrolledtext.ScrolledText(main_frame, 
                                            font=("Consolas", 11),
                                            bg='white',
                                            fg='black',
                                            relief='solid',
                                            borderwidth=2,
                                            padx=10, pady=10)
        text_area.grid(row=1, column=0, sticky='nsew', pady=(0, 15))
        
        # Load current content with better error handling
        try:
            current_content = text_widget.get('1.0', tk.END).strip()
            if current_content:
                text_area.insert('1.0', current_content)
                print(f"✅ Loaded existing content: {len(current_content.split())} lines")
            else:
                print("ℹ️ No existing content to load")
        except Exception as e:
            print(f"⚠️ Error loading content: {e}")
        
        # Button frame
        button_frame = tk.Frame(main_frame, bg='white')
        button_frame.grid(row=2, column=0, sticky='ew')
        
        def save_content():
            """Save content without closing the editor"""
            try:
                # Get content and save to hidden widget
                content = text_area.get('1.0', tk.END).strip()
                text_widget.delete('1.0', tk.END)
                text_widget.insert('1.0', content)
                
                # Update display entry
                lines = [line.strip() for line in content.split('\n') if line.strip()] if content else []
                display_text = f"{len(lines)} items" if lines else "No items"
                
                display_widget.configure(state='normal')
                display_widget.delete(0, tk.END)
                display_widget.insert(0, display_text)
                display_widget.configure(state='readonly')
                
                # Also save to config file immediately
                self.save_config()
                
                # Show success message in the editor
                messagebox.showinfo("Saved", f"✅ Successfully saved {len(lines)} items!")
                print(f"✅ Saved {len(lines)} items successfully!")
                
            except Exception as e:
                messagebox.showerror("Save Error", f"❌ Error saving: {e}")
                print(f"❌ Error saving: {e}")

        def save_and_close():
            """Save content and close the editor"""
            try:
                # Get content and save to hidden widget
                content = text_area.get('1.0', tk.END).strip()
                text_widget.delete('1.0', tk.END)
                text_widget.insert('1.0', content)
                
                # Update display entry
                lines = [line.strip() for line in content.split('\n') if line.strip()] if content else []
                display_text = f"{len(lines)} items" if lines else "No items"
                
                display_widget.configure(state='normal')
                display_widget.delete(0, tk.END)
                display_widget.insert(0, display_text)
                display_widget.configure(state='readonly')
                
                # Also save to config file immediately
                self.save_config()
                
                print(f"✅ Saved {len(lines)} items and closed editor!")
                editor.destroy()
                
            except Exception as e:
                messagebox.showerror("Save Error", f"❌ Error saving: {e}")
                print(f"❌ Error saving: {e}")
                
        def cancel():
            editor.destroy()
            
        # Create buttons with clear styling - Enhanced with proper layout
        print("🔧 Creating editor buttons...")
        
        # Center the buttons with proper spacing
        button_container = tk.Frame(button_frame, bg='white')
        button_container.pack(expand=True, pady=5)
        
        cancel_btn = tk.Button(button_container, text="❌ Cancel", command=cancel,
                              bg='#ef4444', fg='white', font=("Segoe UI", 11),
                              padx=30, pady=12, relief='raised', borderwidth=2)
        cancel_btn.pack(side='left', padx=10)
        print("✅ Cancel button created")
        
        save_only_btn = tk.Button(button_container, text="💾 Save", command=save_content,
                                 bg='#2563eb', fg='white', font=("Segoe UI", 11, "bold"),
                                 padx=30, pady=12, relief='raised', borderwidth=2)
        save_only_btn.pack(side='right', padx=10)
        print("✅ Save button created")
        
        save_close_btn = tk.Button(button_container, text="💾 Save & Close", command=save_and_close,
                                  bg='#10b981', fg='white', font=("Segoe UI", 11, "bold"),
                                  padx=30, pady=12, relief='raised', borderwidth=2)
        save_close_btn.pack(side='right', padx=10)
        print("✅ Save & Close button created")
        
        print("🎯 All editor buttons created successfully!")
        
        # Focus on text area and center window
        text_area.focus_set()
        
        # Center the window on parent
        editor.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (editor.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (editor.winfo_height() // 2)
        editor.geometry(f"+{x}+{y}")
        
        # Bring to front
        editor.lift()
        editor.attributes('-topmost', True)
        editor.after(100, lambda: editor.attributes('-topmost', False))

    def update_banned_displays(self):
        """Update the display entries to show current counts"""
        # Update banned keywords display
        content = self.vars['banned_words'].get('1.0', tk.END).strip()
        lines = [line.strip() for line in content.split('\n') if line.strip()] if content else []
        display_text = f"{len(lines)} keywords" if lines else "No keywords"
        self.banned_keywords_display.configure(state='normal')
        self.banned_keywords_display.delete(0, tk.END)
        self.banned_keywords_display.insert(0, display_text)
        self.banned_keywords_display.configure(state='readonly')
        
        # Update banned companies display
        content = self.vars['banned_companies'].get('1.0', tk.END).strip()
        lines = [line.strip() for line in content.split('\n') if line.strip()] if content else []
        display_text = f"{len(lines)} companies" if lines else "No companies"
        self.banned_companies_display.configure(state='normal')
        self.banned_companies_display.delete(0, tk.END)
        self.banned_companies_display.insert(0, display_text)
        self.banned_companies_display.configure(state='readonly')

if __name__ == "__main__":
    if not os.path.exists(CONFIG_PATH):
         messagebox.showerror("Config Error", f"{CONFIG_PATH} not found. Cannot start GUI.")
    else:
        app = AppConfigurator()
        app.mainloop()
