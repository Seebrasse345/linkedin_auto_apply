import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import yaml
import subprocess
import threading
import os
import sys
import logging

CONFIG_PATH = 'config.yml'
MAIN_SCRIPT_PATH = 'main.py'

TOOLTIPS = {
    # Credentials
    'username': 'Your LinkedIn email address.',
    'password': 'Your LinkedIn password. Stored in config.yml.',
    # Search Profile (Primary)
    'query': 'Keywords for job search (e.g., \'Data Analyst\'). Blank if using auto features.',
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
    'headless': 'Run browser invisibly (True) or visibly (False).',
    'accept_cookies_selector': 'CSS selector for cookie accept button.',
    'random_delay_ms': 'Min/Max delay (ms) between actions.',
    'max_tabs': 'Max simultaneous job tabs.',
    'log_level': 'Logging detail (DEBUG, INFO, WARNING, ERROR).',
    'proxy_pool': 'Proxies (one per line, user:pass@host:port or host:port). Optional.'
}

LOCATION_GEOID_MAP = {
    "United Kingdom": 101165590,
    "Sheffield": 104470941
}

class Tooltip:
    # ... (Tooltip class definition - concise version)
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_win = None
        self.widget.bind("<Enter>", self.show, add='+')
        self.widget.bind("<Leave>", self.hide, add='+')

    def show(self, event=None):
        if self.tooltip_win or not self.text: return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tooltip_win = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify='left', background="#ffffe0",
                         relief='solid', borderwidth=1, wraplength=250)
        label.pack(ipadx=1)

    def hide(self, event=None):
        if self.tooltip_win:
            self.tooltip_win.destroy()
        self.tooltip_win = None

class AppConfigurator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LinkedIn Bot Configurator")
        self.geometry("750x650")

        self.config_data = self.load_config()
        self.vars = {}

        style = ttk.Style(self)
        style.configure('TButton', padding=5)
        style.configure('TFrame', padding=5)
        style.configure('TLabelframe', padding=5, labelmargins=5)

        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(expand=True, fill='both')

        notebook = ttk.Notebook(main_frame)
        notebook.pack(expand=True, fill='both', pady=5)

        self.create_core_tab(notebook)
        self.create_filters_tab(notebook)
        self.create_runtime_tab(notebook)

        self.start_button = ttk.Button(main_frame, text="Save Config & Start Bot", command=self.start_bot)
        self.start_button.pack(pady=10)

        self.load_values_from_config()

    def add_tooltip(self, widget, key):
        if key in TOOLTIPS: Tooltip(widget, TOOLTIPS[key])

    def create_entry(self, parent, key, label_text, row, col, widget_kwargs=None, grid_kwargs=None):
        if widget_kwargs is None: widget_kwargs = {}
        if grid_kwargs is None: grid_kwargs = {}
        
        # Default grid settings
        grid_params = {'row': row, 'column': col + 1, 'sticky': 'ew', 'padx': 5, 'pady': 2}
        grid_params.update(grid_kwargs) # Override defaults with provided kwargs
        
        ttk.Label(parent, text=label_text).grid(row=row, column=col, sticky='w', padx=5, pady=2)
        # Ensure textvariable is passed correctly if provided
        if 'textvariable' not in widget_kwargs:
             self.vars[key] = tk.StringVar()
             widget_kwargs['textvariable'] = self.vars[key]
        elif key not in self.vars: # If textvariable provided, ensure self.vars key exists
             self.vars[key] = widget_kwargs['textvariable']
             
        # Pass only widget-specific kwargs here
        entry = ttk.Entry(parent, **widget_kwargs)
        entry.grid(**grid_params) # Apply grid settings here
        self.add_tooltip(entry, key)
        return entry

    def create_checkbox(self, parent, key, label_text, row, col, widget_kwargs=None, grid_kwargs=None):
        if widget_kwargs is None: widget_kwargs = {}
        if grid_kwargs is None: grid_kwargs = {}

        # Default grid settings
        grid_params = {'row': row, 'column': col, 'sticky': 'w', 'padx': 5, 'pady': 2}
        grid_params.update(grid_kwargs)
        
        self.vars[key] = tk.BooleanVar()
        cb = ttk.Checkbutton(parent, text=label_text, variable=self.vars[key], **widget_kwargs)
        cb.grid(**grid_params)
        self.add_tooltip(cb, key)
        return cb

    def create_combobox(self, parent, key, label_text, values, row, col, widget_kwargs=None, grid_kwargs=None):
        if widget_kwargs is None: widget_kwargs = {}
        if grid_kwargs is None: grid_kwargs = {}
        
        grid_params = {'row': row, 'column': col + 1, 'sticky': 'ew', 'padx': 5, 'pady': 2}
        grid_params.update(grid_kwargs)

        # Ensure 'state' defaults to 'readonly' if not provided
        if 'state' not in widget_kwargs:
            widget_kwargs['state'] = 'readonly'
            
        # Ensure textvariable is passed correctly if provided
        if 'textvariable' not in widget_kwargs:
            self.vars[key] = tk.StringVar()
            widget_kwargs['textvariable'] = self.vars[key]
        elif key not in self.vars:
             self.vars[key] = widget_kwargs['textvariable']

        ttk.Label(parent, text=label_text).grid(row=row, column=col, sticky='w', padx=5, pady=2)
        combo = ttk.Combobox(parent, values=values, **widget_kwargs)
        combo.grid(**grid_params)
        self.add_tooltip(combo, key)
        return combo

    def create_scrolledtext(self, parent, key, height=5, width=40):
        # ScrolledText uses pack or grid on itself, not a separate helper
        st = scrolledtext.ScrolledText(parent, wrap=tk.WORD, height=height, width=width)
        st.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        self.add_tooltip(st, key)
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        self.vars[key] = st # Store widget directly
        return st

    def create_core_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=10)
        notebook.add(tab, text='Core Settings')

        cred_frame = ttk.LabelFrame(tab, text="Credentials", padding=10)
        cred_frame.pack(fill='x', pady=5)
        # Pass widget-specific args like width in widget_kwargs
        self.create_entry(cred_frame, 'username', "Username:", 0, 0, widget_kwargs={'width': 40})
        self.create_entry(cred_frame, 'password', "Password:", 1, 0, widget_kwargs={'width': 40, 'show': '*'}) 
        cred_frame.columnconfigure(1, weight=1)

        search_frame = ttk.LabelFrame(tab, text="Search Profile (Primary)", padding=10)
        search_frame.pack(fill='x', pady=5)
        # Pass columnspan via grid_kwargs
        self.create_entry(search_frame, 'query', "Query:", 0, 0, 
                        widget_kwargs={'width': 50}, 
                        grid_kwargs={'columnspan': 3}) 

        # Location Combobox (handled separately as it needs binding)
        ttk.Label(search_frame, text="Location:").grid(row=1, column=0, sticky='w', padx=5, pady=2)
        self.vars['location'] = tk.StringVar()
        locations = list(LOCATION_GEOID_MAP.keys()) + ["Other (Manual GeoID)"]
        # Pass width directly to Combobox constructor
        location_combo = ttk.Combobox(search_frame, textvariable=self.vars['location'], values=locations, width=25)
        location_combo.grid(row=1, column=1, sticky='ew', padx=5, pady=2)
        location_combo.bind('<<ComboboxSelected>>', self.update_geoId)
        location_combo.bind('<KeyRelease>', self.update_geoId)
        self.add_tooltip(location_combo, 'location')

        # GeoID Entry (handled separately as it needs a reference)
        ttk.Label(search_frame, text="GeoID:").grid(row=1, column=2, sticky='w', padx=5, pady=2)
        self.vars['geoId'] = tk.StringVar()
        self.geoId_entry = ttk.Entry(search_frame, textvariable=self.vars['geoId'], width=15)
        self.geoId_entry.grid(row=1, column=3, sticky='ew', padx=5, pady=2)
        self.add_tooltip(self.geoId_entry, 'geoId')

        auto_frame = ttk.Frame(search_frame)
        auto_frame.grid(row=2, column=0, columnspan=4, sticky='w', pady=5)
        # Checkbuttons use pack within their own frame, so grid_kwargs aren't needed here
        # We call the base ttk.Checkbutton directly for packing layout control
        self.vars['auto_easy'] = tk.BooleanVar()
        cb_easy = ttk.Checkbutton(auto_frame, text="Use Easy Apply List", variable=self.vars['auto_easy'])
        cb_easy.pack(side=tk.LEFT, padx=5)
        self.add_tooltip(cb_easy, 'auto_easy')

        self.vars['auto_recommend'] = tk.BooleanVar()
        cb_rec = ttk.Checkbutton(auto_frame, text="Use Recommended List", variable=self.vars['auto_recommend'])
        cb_rec.pack(side=tk.LEFT, padx=5)
        self.add_tooltip(cb_rec, 'auto_recommend')

        search_frame.columnconfigure(1, weight=1)
        search_frame.columnconfigure(3, weight=1)

    def create_filters_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=10)
        notebook.add(tab, text='Search Filters')

        filter_frame = ttk.LabelFrame(tab, text="Job Filters", padding=10)
        filter_frame.pack(fill='both', expand=True, pady=5)

        basic_frame = ttk.Frame(filter_frame)
        basic_frame.grid(row=0, column=0, sticky='nsew', padx=10)
        multi_frame = ttk.Frame(filter_frame)
        multi_frame.grid(row=0, column=1, sticky='nsew', padx=10)
        filter_frame.columnconfigure(0, weight=1)
        filter_frame.columnconfigure(1, weight=1)

        # Basic Filters - Pass width via widget_kwargs
        self.vars['distance_km'] = tk.IntVar() # Needs setup before create_combobox
        self.create_combobox(basic_frame, 'distance_km', "Distance (km):", [8, 15, 40, 80], 0, 0, 
                             widget_kwargs={'width': 10, 'textvariable': self.vars['distance_km']}) 
        self.create_combobox(basic_frame, 'date_posted', "Date Posted:", ["past_24h", "past_week", "past_month", "any_time"], 1, 0, 
                             widget_kwargs={'width': 15})
        # Pass columnspan via grid_kwargs
        self.create_checkbox(basic_frame, 'low_number_applicants', "Low Number Applicants Filter", 2, 0, grid_kwargs={'columnspan': 2})
        basic_frame.columnconfigure(1, weight=1)

        # Multi-Select Filters (These manage their own grid internally)
        self.vars['remote'] = self._create_multi_check(multi_frame, 'remote', "Remote Options", ["on_site", "remote", "hybrid"])
        self.vars['experience'] = self._create_multi_check(multi_frame, 'experience', "Experience Levels", ["internship", "entry_level", "associate", "mid_senior_level", "director", "executive"], cols=2)
        self.vars['job_type'] = self._create_multi_check(multi_frame, 'job_type', "Job Types", ["full_time", "part_time", "contract", "temporary", "volunteer", "internship"], cols=2)

    def _create_multi_check(self, parent, key, label_text, options, cols=3):
        frame = ttk.LabelFrame(parent, text=label_text)
        frame.pack(fill='x', pady=3)
        self.add_tooltip(frame, key)
        vars_dict = {}
        for i, option in enumerate(options):
            var = tk.BooleanVar()
            cb = ttk.Checkbutton(frame, text=option.replace('_', ' ').title(), variable=var)
            # Grid inside the LabelFrame
            cb.grid(row=i // cols, column=i % cols, sticky='w', padx=5, pady=1)
            vars_dict[option] = var
        return vars_dict

    def create_runtime_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=10)
        notebook.add(tab, text='Runtime & Advanced')
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1) # Banned words expands
        tab.rowconfigure(2, weight=1) # Proxy pool expands

        runtime_frame = ttk.LabelFrame(tab, text="Runtime Settings", padding=10)
        runtime_frame.grid(row=0, column=0, sticky='ew', padx=5, pady=5)

        self.create_checkbox(runtime_frame, 'headless', "Run Headless", 0, 0, grid_kwargs={'columnspan': 2}) # Use columnspan here
        self.create_entry(runtime_frame, 'accept_cookies_selector', "Cookie Selector:", 1, 0, widget_kwargs={'width': 25})
        
        # Delay frame uses pack, handle directly
        delay_frame = ttk.Frame(runtime_frame)
        delay_frame.grid(row=2, column=0, columnspan=2, sticky='ew')
        ttk.Label(delay_frame, text="Random Delay (ms):").pack(side=tk.LEFT, padx=5, pady=2)
        self.vars['random_delay_ms_min'] = tk.IntVar()
        min_entry = ttk.Entry(delay_frame, textvariable=self.vars['random_delay_ms_min'], width=7)
        min_entry.pack(side=tk.LEFT, padx=2)
        self.add_tooltip(min_entry, 'random_delay_ms')
        ttk.Label(delay_frame, text="-").pack(side=tk.LEFT, padx=1)
        self.vars['random_delay_ms_max'] = tk.IntVar()
        max_entry = ttk.Entry(delay_frame, textvariable=self.vars['random_delay_ms_max'], width=7)
        max_entry.pack(side=tk.LEFT, padx=2)
        self.add_tooltip(max_entry, 'random_delay_ms')

        self.vars['max_tabs'] = tk.IntVar() # Needs setup before create_entry
        self.create_entry(runtime_frame, 'max_tabs', "Max Job Tabs:", 3, 0, 
                          widget_kwargs={'width': 5, 'textvariable': self.vars['max_tabs']}, 
                          grid_kwargs={'sticky':'w'}) # Make sticky w
        self.create_combobox(runtime_frame, 'log_level', "Log Level:", ["DEBUG", "INFO", "WARNING", "ERROR"], 4, 0, 
                             widget_kwargs={'width': 10}, 
                             grid_kwargs={'sticky':'w'}) # Make sticky w
        runtime_frame.columnconfigure(1, weight=1)

        # ScrolledText frames manage their own grid/pack
        banned_frame = ttk.LabelFrame(tab, text="Banned Keywords", padding=10)
        banned_frame.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        self.create_scrolledtext(banned_frame, 'banned_words', height=6)

        proxy_frame = ttk.LabelFrame(tab, text="Proxy Pool (Optional)", padding=10)
        proxy_frame.grid(row=2, column=0, sticky='nsew', padx=5, pady=5)
        self.create_scrolledtext(proxy_frame, 'proxy_pool', height=4)

    def update_geoId(self, event=None):
        loc = self.vars['location'].get()
        if loc in LOCATION_GEOID_MAP:
            self.vars['geoId'].set(LOCATION_GEOID_MAP[loc])
            self.geoId_entry.config(state='readonly')
        else:
            if self.geoId_entry.cget('state') == 'readonly': # If switching from mapped
                self.vars['geoId'].set("")
            self.geoId_entry.config(state='normal')

    def load_config(self):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            return {} # Return empty dict if not found, allow defaults
        except yaml.YAMLError as e:
             messagebox.showerror("Config Error", f"Error parsing {CONFIG_PATH}:\n{e}")
             return None # Indicate failure

    def load_values_from_config(self):
        if self.config_data is None: return # Load failed
        cfg = self.config_data

        # Credentials
        self.vars['username'].set(cfg.get('credentials', {}).get('username', ''))
        self.vars['password'].set(cfg.get('credentials', {}).get('password', ''))

        # Search Profile (first one)
        profile = cfg.get('search_profiles', [{}])[0]
        self.vars['query'].set(profile.get('query', ''))
        loc = profile.get('location', '')
        self.vars['location'].set(loc if loc in LOCATION_GEOID_MAP or not loc else 'Other (Manual GeoID)')
        self.update_geoId() # Set GeoID based on location
        if loc not in LOCATION_GEOID_MAP: # If custom, load saved GeoID
             self.vars['geoId'].set(profile.get('geoId', ''))

        filters = profile.get('filters', {})
        self.vars['distance_km'].set(filters.get('distance_km', 15))
        self.vars['date_posted'].set(filters.get('date_posted', 'past_24h'))
        self.vars['low_number_applicants'].set(filters.get('low_number_applicants', False))
        self.vars['auto_easy'].set(filters.get('auto_easy', False))
        self.vars['auto_recommend'].set(filters.get('auto_recommend', False))

        for key, var_dict in [('remote', self.vars['remote']), ('experience', self.vars['experience']), ('job_type', self.vars['job_type'])]:
            selected = filters.get(key, [])
            if isinstance(selected, list): # Ensure list
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

        # Banned Words & Proxy Pool (ScrolledText)
        for key in ['banned_words', 'proxy_pool']:
            # Determine correct place to get data from config
            if key == 'banned_words':
                # Get 'banned_words' directly from cfg, default to empty list
                data_list = cfg.get(key, [])
            elif key == 'proxy_pool':
                # Get 'proxy_pool' from runtime section, default to empty list
                data_list = cfg.get('runtime', {}).get(key, [])
            else:
                data_list = [] # Should not happen with current loop

            if not isinstance(data_list, list): data_list = [] # Ensure it's a list
            widget = self.vars[key]
            widget.delete('1.0', tk.END)
            widget.insert('1.0', '\n'.join(data_list))

    def save_config(self):
        if self.config_data is None: return False # Don't save if load failed
        cfg = self.config_data # Modify loaded data

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
        profile['location'] = loc if loc != 'Other (Manual GeoID)' else '' # Store empty if other was selected
        profile['geoId'] = int(self.vars['geoId'].get()) if self.vars['geoId'].get().isdigit() else self.vars['geoId'].get() # Store as int if possible

        if 'filters' not in profile: profile['filters'] = {}
        filters = profile['filters']
        filters['distance_km'] = self.vars['distance_km'].get()
        filters['date_posted'] = self.vars['date_posted'].get()
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

        # Banned Words & Proxy Pool
        for key in ['banned_words', 'proxy_pool']:
            widget = self.vars[key]
            data = widget.get('1.0', tk.END).strip().split('\n')
            data = [line for line in data if line] # Remove empty lines
            if key == 'banned_words':
                cfg[key] = data
            else: # proxy_pool is under runtime
                 runtime[key] = data

        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
            return True
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save {CONFIG_PATH}:\n{e}")
            return False

    def run_main_script(self):
        try:
            # Ensure using the python executable that runs the GUI
            python_executable = sys.executable
            process = subprocess.Popen([python_executable, MAIN_SCRIPT_PATH], 
                                       stdout=subprocess.PIPE, 
                                       stderr=subprocess.PIPE,
                                       text=True, 
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

            # Non-blocking read of stdout/stderr if needed, or just let it run
            print(f"Starting {MAIN_SCRIPT_PATH}...")
            # You could add more complex process monitoring here if required
            stdout, stderr = process.communicate()
            print(f"{MAIN_SCRIPT_PATH} finished.")
            if stdout:
                print("Output:\n", stdout)
            if stderr:
                print("Errors:\n", stderr, file=sys.stderr)
            
            # Re-enable button after script finishes
            self.start_button.config(state=tk.NORMAL, text="Save Config & Start Bot") 

        except FileNotFoundError:
            messagebox.showerror("Error", f"{MAIN_SCRIPT_PATH} not found.")
            self.start_button.config(state=tk.NORMAL, text="Save Config & Start Bot")
        except Exception as e:
            messagebox.showerror("Execution Error", f"Error running {MAIN_SCRIPT_PATH}:\n{e}")
            self.start_button.config(state=tk.NORMAL, text="Save Config & Start Bot")
        finally:
             # Ensure button is re-enabled in case of unexpected issues within the thread
             if hasattr(self, 'start_button') and self.start_button.winfo_exists():
                self.start_button.config(state=tk.NORMAL, text="Save Config & Start Bot") 

    def start_bot(self):
        if not self.save_config():
            return # Don't start if save failed

        self.start_button.config(state=tk.DISABLED, text="Bot Running...")
        
        # Run main.py in a separate thread to avoid blocking the GUI
        thread = threading.Thread(target=self.run_main_script, daemon=True)
        thread.start()

if __name__ == "__main__":
    if not os.path.exists(CONFIG_PATH):
         messagebox.showerror("Config Error", f"{CONFIG_PATH} not found. Cannot start GUI.")
    else:
        app = AppConfigurator()
        app.mainloop()
