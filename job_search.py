import tkinter as tk
from tkinter import ttk, scrolledtext
import json
import os
import datetime
import re
from functools import partial
from tkcalendar import DateEntry  # For calendar widget

# Modern color scheme matching the main GUI
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

class JobSearchApp(tk.Toplevel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.title("🔍 LinkedIn Job Search & Analytics")
        self.geometry("1200x750")
        self.minsize(900, 600)
        self.configure(bg=COLORS['background'])
        
        # Load job data
        self.job_data = self.load_job_data()
        self.filtered_jobs = self.job_data.copy()
        
        # For column sorting
        self.current_sort = {
            "column": None,
            "reverse": False
        }
        
        # Setup modern styling
        self.setup_styles()
        
        # Setup UI components
        self.create_widgets()
        self.apply_filters()
        
    def setup_styles(self):
        """Configure modern styling for the job search window"""
        style = ttk.Style(self)
        
        # Try to use a more modern theme if available
        try:
            style.theme_use('clam')
        except:
            style.theme_use('default')
        
        # Configure styles to match main GUI
        style.configure('Modern.TFrame', 
                       background=COLORS['surface'],
                       relief='flat',
                       borderwidth=1)
        
        style.configure('Card.TLabelframe', 
                       background=COLORS['surface'],
                       relief='solid',
                       borderwidth=1,
                       labelmargins=(15, 8, 15, 8))
        
        style.configure('Card.TLabelframe.Label',
                       background=COLORS['surface'],
                       foreground=COLORS['text_primary'],
                       font=("Segoe UI", 11, "bold"))
        
        # Enhanced button styles
        style.configure('Primary.TButton',
                       background=COLORS['primary'],
                       foreground='white',
                       font=("Segoe UI", 10, "bold"),
                       padding=(16, 10),
                       relief='flat',
                       borderwidth=0)
        
        style.map('Primary.TButton',
                 background=[('active', COLORS['primary_hover']),
                           ('pressed', COLORS['primary_hover'])])
        
        style.configure('Success.TButton',
                       background=COLORS['accent'],
                       foreground='white',
                       font=("Segoe UI", 10, "bold"),
                       padding=(16, 10),
                       relief='flat',
                       borderwidth=0)
        
        style.map('Success.TButton',
                 background=[('active', COLORS['accent_hover']),
                           ('pressed', COLORS['accent_hover'])])
        
        # Enhanced entry styles
        style.configure('Modern.TEntry',
                       fieldbackground=COLORS['surface'],
                       borderwidth=1,
                       relief='solid',
                       padding=(10, 8),
                       font=("Segoe UI", 10))
        
        style.map('Modern.TEntry',
                 focuscolor=[('!focus', COLORS['border'])],
                 bordercolor=[('focus', COLORS['primary'])])
        
        # Enhanced label styles
        style.configure('Header.TLabel',
                       background=COLORS['surface'],
                       foreground=COLORS['text_primary'],
                       font=("Segoe UI", 11, "bold"),
                       padding=(0, 8))
        
        style.configure('Body.TLabel',
                       background=COLORS['surface'],
                       foreground=COLORS['text_secondary'],
                       font=("Segoe UI", 10),
                       padding=(0, 4))
        
        style.configure('Info.TLabel',
                       background=COLORS['surface_secondary'],
                       foreground=COLORS['text_secondary'],
                       font=("Segoe UI", 9),
                       padding=(8, 6),
                       relief='solid',
                       borderwidth=1)
        
        # Enhanced treeview styles
        style.configure('Modern.Treeview',
                       background=COLORS['surface'],
                       foreground=COLORS['text_primary'],
                       fieldbackground=COLORS['surface'],
                       font=("Segoe UI", 10),
                       rowheight=30)
        
        style.configure('Modern.Treeview.Heading',
                       background=COLORS['surface_secondary'],
                       foreground=COLORS['text_primary'],
                       font=("Segoe UI", 10, "bold"),
                       relief='solid',
                       borderwidth=1)
        
        style.map('Modern.Treeview',
                 background=[('selected', COLORS['primary'])],
                 foreground=[('selected', 'white')])
        
        style.map('Modern.Treeview.Heading',
                 background=[('active', COLORS['border'])])

    def load_job_data(self):
        """Load job descriptions from JSON file"""
        try:
            data_path = os.path.join('data', 'job_descriptions_applied.json')
            if os.path.exists(data_path):
                with open(data_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print(f"Warning: Job data file not found at {data_path}")
                return []
        except Exception as e:
            print(f"Error loading job data: {e}")
            return []
    
    def create_widgets(self):
        """Create the main UI components with enhanced styling"""
        # Main frame with modern styling
        main_frame = ttk.Frame(self, style='Modern.TFrame', padding="12")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title header
        title_frame = ttk.Frame(main_frame, style='Modern.TFrame')
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        title_label = ttk.Label(title_frame, 
                               text="Job Search & Analytics Dashboard",
                               font=("Segoe UI", 16, "bold"),
                               foreground=COLORS['primary'],
                               background=COLORS['surface'])
        title_label.pack(side=tk.LEFT)
        
        # Stats label
        self.stats_var = tk.StringVar()
        stats_label = ttk.Label(title_frame,
                               textvariable=self.stats_var,
                               font=("Segoe UI", 11),
                               foreground=COLORS['text_secondary'],
                               background=COLORS['surface'])
        stats_label.pack(side=tk.RIGHT)
        
        # Compact search filters section
        filter_frame = ttk.LabelFrame(main_frame, text="🔍 Search Filters", style='Card.TLabelframe', padding="10")
        filter_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Create a compact grid layout for filters  
        # Row 1: Title and Company (smaller)
        ttk.Label(filter_frame, text="📝 Title:", font=("Segoe UI", 9)).grid(row=0, column=0, sticky=tk.W, padx=(0, 5), pady=4)
        self.title_var = tk.StringVar()
        title_entry = ttk.Entry(filter_frame, textvariable=self.title_var, width=20, font=("Segoe UI", 9))
        title_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, 15), pady=4)
        self.title_var.trace("w", lambda *args: self.apply_filters())
        
        ttk.Label(filter_frame, text="🏢 Company:", font=("Segoe UI", 9)).grid(row=0, column=2, sticky=tk.W, padx=(0, 5), pady=4)
        self.company_var = tk.StringVar()
        company_entry = ttk.Entry(filter_frame, textvariable=self.company_var, width=20, font=("Segoe UI", 9))
        company_entry.grid(row=0, column=3, sticky=tk.EW, padx=(0, 15), pady=4)
        self.company_var.trace("w", lambda *args: self.apply_filters())
        
        # Row 2: Keywords and Date Range (smaller)
        ttk.Label(filter_frame, text="🔍 Keywords:", font=("Segoe UI", 9)).grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=4)
        self.keywords_var = tk.StringVar()
        keywords_entry = ttk.Entry(filter_frame, textvariable=self.keywords_var, width=20, font=("Segoe UI", 9))
        keywords_entry.grid(row=1, column=1, sticky=tk.EW, padx=(0, 15), pady=4)
        self.keywords_var.trace("w", lambda *args: self.apply_filters())
        
        # Compact date range with calendar widgets
        ttk.Label(filter_frame, text="📅 Dates:", font=("Segoe UI", 9)).grid(row=1, column=2, sticky=tk.W, padx=(0, 5), pady=4)
        
        date_frame = ttk.Frame(filter_frame)
        date_frame.grid(row=1, column=3, sticky=tk.EW, padx=(0, 15), pady=4)
        
        # From date with calendar (starts empty)
        ttk.Label(date_frame, text="From:", font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(0, 4))
        try:
            self.from_date_picker = DateEntry(date_frame, width=10, background=COLORS['primary'],
                                            foreground='white', borderwidth=1, 
                                            font=("Segoe UI", 8), date_pattern='yyyy-mm-dd')
            self.from_date_picker.pack(side=tk.LEFT, padx=(0, 10))
            self.from_date_picker.bind('<<DateEntrySelected>>', lambda e: self.apply_filters())
            # Set to None/empty by default as requested
            self.from_date_picker.set_date(None)
        except:
            # Fallback to regular entry if tkcalendar is not available
            self.from_date_var = tk.StringVar()
            from_entry = ttk.Entry(date_frame, textvariable=self.from_date_var, width=10, font=("Segoe UI", 8))
            from_entry.pack(side=tk.LEFT, padx=(0, 10))
            self.from_date_var.trace("w", lambda *args: self.apply_filters())
        
        # To date with calendar
        ttk.Label(date_frame, text="To:", font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(0, 4))
        try:
            self.to_date_picker = DateEntry(date_frame, width=10, background=COLORS['primary'],
                                          foreground='white', borderwidth=1,
                                          font=("Segoe UI", 8), date_pattern='yyyy-mm-dd')
            self.to_date_picker.pack(side=tk.LEFT)
            self.to_date_picker.bind('<<DateEntrySelected>>', lambda e: self.apply_filters())
            # Set to None/empty by default as requested  
            self.to_date_picker.set_date(None)
        except:
            # Fallback to regular entry if tkcalendar is not available
            self.to_date_var = tk.StringVar()
            to_entry = ttk.Entry(date_frame, textvariable=self.to_date_var, width=10, font=("Segoe UI", 8))
            to_entry.pack(side=tk.LEFT)
            self.to_date_var.trace("w", lambda *args: self.apply_filters())
        
        # Row 3: Compact buttons and status
        button_frame = ttk.Frame(filter_frame)
        button_frame.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))
        
        reset_btn = ttk.Button(button_frame, text="🔄 Reset", command=self.reset_filters, width=8)
        reset_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        export_btn = ttk.Button(button_frame, text="📊 Export", command=self.export_results, width=8)
        export_btn.pack(side=tk.LEFT)
        
        # Status and results count
        self.status_var = tk.StringVar()
        status_label = ttk.Label(filter_frame, textvariable=self.status_var, font=("Segoe UI", 9))
        status_label.grid(row=2, column=2, columnspan=2, sticky=tk.E, pady=(8, 0))
        
        # Configure column weights for responsive design
        filter_frame.columnconfigure(1, weight=1)
        filter_frame.columnconfigure(3, weight=1)
        
        # Create the enhanced paned window for results and details
        paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)
        
        # Left side - Enhanced job results list
        results_frame = ttk.LabelFrame(paned_window, text="📋 Job Results", style='Card.TLabelframe', padding="15")
        paned_window.add(results_frame, weight=40)
        
        # Treeview for job results with enhanced styling
        self.tree_frame = ttk.Frame(results_frame, style='Modern.TFrame')
        self.tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Enhanced scrollbar
        tree_scrollbar = ttk.Scrollbar(self.tree_frame)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Enhanced job results treeview
        self.results_tree = ttk.Treeview(
            self.tree_frame,
            columns=("title", "company", "date"),
            show="headings",
            selectmode="browse",
            height=20,
            style='Modern.Treeview'
        )
        
        # Configure scrollbar
        tree_scrollbar.config(command=self.results_tree.yview)
        self.results_tree.config(yscrollcommand=tree_scrollbar.set)
        
        # Define enhanced columns with emojis
        self.results_tree.heading("title", text="📝 Job Title", command=lambda: self.sort_treeview("title", False))
        self.results_tree.heading("company", text="🏢 Company", command=lambda: self.sort_treeview("company", False))
        self.results_tree.heading("date", text="📅 Date Posted", command=lambda: self.sort_treeview("date", True))
        
        # Enhanced column widths
        self.results_tree.column("title", width=400)
        self.results_tree.column("company", width=250)
        self.results_tree.column("date", width=150)
        
        self.results_tree.pack(fill=tk.BOTH, expand=True)
        self.results_tree.bind('<<TreeviewSelect>>', self.display_job_details)
        
        # Right side - Enhanced job details
        detail_frame = ttk.LabelFrame(paned_window, text="📄 Job Details", style='Card.TLabelframe', padding="15")
        paned_window.add(detail_frame, weight=60)
        
        # Enhanced job header frame
        job_header_frame = ttk.Frame(detail_frame, style='Modern.TFrame', padding=15)
        job_header_frame.pack(fill=tk.X, pady=(0, 15))
        job_header_frame.configure(relief='solid', borderwidth=1)
        
        # Job title with enhanced styling
        self.job_title_var = tk.StringVar()
        job_title_label = ttk.Label(job_header_frame, textvariable=self.job_title_var, 
                                   font=("Segoe UI", 16, "bold"), 
                                   foreground=COLORS['primary'],
                                   background=COLORS['surface'])
        job_title_label.pack(anchor=tk.W, pady=(0, 8))
        
        # Company with enhanced styling
        self.job_company_var = tk.StringVar()
        job_company_label = ttk.Label(job_header_frame, textvariable=self.job_company_var, 
                                     font=("Segoe UI", 12, "bold"),
                                     foreground=COLORS['text_primary'],
                                     background=COLORS['surface'])
        job_company_label.pack(anchor=tk.W, pady=(0, 8))
        
        # Date and match info
        info_frame = ttk.Frame(job_header_frame, style='Modern.TFrame')
        info_frame.pack(fill=tk.X)
        
        self.job_date_var = tk.StringVar()
        job_date_label = ttk.Label(info_frame, textvariable=self.job_date_var,
                                  font=("Segoe UI", 10),
                                  foreground=COLORS['text_secondary'],
                                  background=COLORS['surface'])
        job_date_label.pack(side=tk.LEFT)
        
        self.job_match_var = tk.StringVar()
        job_match_label = ttk.Label(info_frame, textvariable=self.job_match_var,
                                   font=("Segoe UI", 10, "bold"),
                                   foreground=COLORS['accent'],
                                   background=COLORS['surface'])
        job_match_label.pack(side=tk.RIGHT)
        
        # Enhanced and bigger job description display
        desc_frame = ttk.Frame(detail_frame, style='Modern.TFrame')
        desc_frame.pack(fill=tk.BOTH, expand=True)
        
        self.job_description_text = scrolledtext.ScrolledText(
            desc_frame, 
            wrap=tk.WORD, 
            width=60, 
            height=30,
            font=("Segoe UI", 11),
            bg=COLORS['surface'],
            fg=COLORS['text_primary'],
            selectbackground=COLORS['primary'],
            selectforeground='white',
            relief='solid',
            borderwidth=2,
            padx=20,
            pady=20
        )
        self.job_description_text.pack(fill=tk.BOTH, expand=True)
        self.job_description_text.config(state=tk.DISABLED)
        
        # Configure enhanced tag for highlighting keywords (bigger font)
        self.job_description_text.tag_configure("highlight", background=COLORS['warning'], foreground="black", font=("Segoe UI", 11, "bold"))
        
        # Update stats on load
        self.update_stats()
    
    def update_stats(self):
        """Update the statistics display"""
        total_jobs = len(self.job_data)
        filtered_jobs = len(self.filtered_jobs)
        
        if total_jobs > 0:
            # Calculate some basic stats
            companies = set(job.get('company', 'Unknown') for job in self.job_data)
            
            # Find date range
            dates = []
            for job in self.job_data:
                if job.get('timestamp'):
                    try:
                        dates.append(datetime.datetime.fromisoformat(job['timestamp']))
                    except:
                        pass
            
            if dates:
                earliest = min(dates).strftime("%Y-%m-%d")
                latest = max(dates).strftime("%Y-%m-%d")
                date_range = f"({earliest} to {latest})"
            else:
                date_range = ""
            
            stats_text = f"📊 {total_jobs} total jobs from {len(companies)} companies {date_range}"
        else:
            stats_text = "📊 No job data loaded"
        
        self.stats_var.set(stats_text)
    
    def export_results(self):
        """Export filtered results to JSON file"""
        if not self.filtered_jobs:
            tk.messagebox.showwarning("Export Warning", "No filtered results to export!")
            return
        
        try:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                title="Export Search Results"
            )
            
            if filename:
                # Prepare export data with additional metadata
                export_data = {
                    "export_timestamp": datetime.datetime.now().isoformat(),
                    "search_filters": {
                        "title": self.title_var.get(),
                        "company": self.company_var.get(),
                        "keywords": self.keywords_var.get(),
                        "from_date": getattr(self, 'from_date_picker', None) and self.from_date_picker.get() or getattr(self, 'from_date_var', tk.StringVar()).get(),
                        "to_date": getattr(self, 'to_date_picker', None) and self.to_date_picker.get() or getattr(self, 'to_date_var', tk.StringVar()).get()
                    },
                    "total_results": len(self.filtered_jobs),
                    "jobs": self.filtered_jobs
                }
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                
                # Success message with modern styling
                success_window = tk.Toplevel(self)
                success_window.title("Export Success")
                success_window.geometry("350x130")
                success_window.configure(bg=COLORS['surface'])
                success_window.resizable(False, False)
                success_window.transient(self)
                success_window.grab_set()
                
                # Center the window
                success_window.update_idletasks()
                x = (success_window.winfo_screenwidth() // 2) - (350 // 2)
                y = (success_window.winfo_screenheight() // 2) - (130 // 2)
                success_window.geometry(f"350x130+{x}+{y}")
                
                message_frame = ttk.Frame(success_window, style='Modern.TFrame', padding=20)
                message_frame.pack(fill='both', expand=True)
                
                success_label = ttk.Label(message_frame, 
                                        text=f"✅ Successfully exported {len(self.filtered_jobs)} jobs!",
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
            tk.messagebox.showerror("Export Error", f"Failed to export results:\n{str(e)}")
    
    def sort_treeview(self, column, is_numeric):
        """Sort treeview contents by a column"""
        # Toggle sort direction if the same column is clicked again
        if self.current_sort["column"] == column:
            self.current_sort["reverse"] = not self.current_sort["reverse"]
        else:
            self.current_sort["column"] = column
            self.current_sort["reverse"] = False
        
        # Update the column headings to show sort direction
        for col in ("title", "company", "date"):
            # Reset the column heading text with emojis
            text_map = {
                "title": "📝 Job Title",
                "company": "🏢 Company", 
                "date": "📅 Date Posted"
            }
            text = text_map.get(col, col.capitalize())
                
            # Add sort indicator
            if col == column:
                text = f"{text} {'↑' if not self.current_sort['reverse'] else '↓'}"
                
            self.results_tree.heading(col, text=text)
        
        # Sort the filtered jobs
        if column == "title":
            self.filtered_jobs.sort(key=lambda job: job.get("title", "").lower(), reverse=self.current_sort["reverse"])
        elif column == "company":
            self.filtered_jobs.sort(key=lambda job: job.get("company", "N/A").lower(), reverse=self.current_sort["reverse"])
        elif column == "date":
            # Sort by timestamp
            def get_date(job):
                try:
                    return datetime.datetime.fromisoformat(job.get("timestamp", "1970-01-01T00:00:00"))
                except (ValueError, TypeError):
                    return datetime.datetime.min
            
            self.filtered_jobs.sort(key=get_date, reverse=self.current_sort["reverse"])
        
        # Refresh the display without refiltering
        self.update_results_view(resort=False)
    
    def apply_filters(self, *args):
        """Apply filters to job data and update the results view"""
        self.filtered_jobs = []
        
        title_filter = self.title_var.get().lower()
        company_filter = self.company_var.get().lower()
        keywords_text = self.keywords_var.get().strip()
        
        # Get dates from either calendar widgets or string variables
        try:
            if hasattr(self, 'from_date_picker'):
                from_date = self.from_date_picker.get()
            else:
                from_date = self.from_date_var.get()
                
            if hasattr(self, 'to_date_picker'):
                to_date = self.to_date_picker.get()
            else:
                to_date = self.to_date_var.get()
        except:
            from_date = ""
            to_date = ""
        
        # Process keywords - split by commas and trim whitespace
        keywords_filter = [kw.strip().lower() for kw in keywords_text.split(',') if kw.strip()] if keywords_text else []
        
        # Parse dates if provided
        try:
            from_date_obj = datetime.datetime.strptime(str(from_date), "%Y-%m-%d") if from_date else None
            to_date_obj = datetime.datetime.strptime(str(to_date), "%Y-%m-%d") if to_date else None
            
            # If to_date is provided, move to end of day
            if to_date_obj:
                to_date_obj = to_date_obj.replace(hour=23, minute=59, second=59)
                
        except ValueError:
            # Invalid date format, just use None
            from_date_obj = None
            to_date_obj = None
        
        # Apply filters
        job_matches = []
        for job in self.job_data:
            job_title = job.get("title", "").lower()
            job_company = job.get("company", "").lower()
            job_description = job.get("description", "").lower()
            
            # Check title and company filters
            title_match = not title_filter or title_filter in job_title
            company_match = not company_filter or company_filter in job_company
            
            # Check keywords - now handling multiple keywords with enhanced matching
            keywords_match = True
            keyword_match_count = 0
            matched_keywords = []
            
            if keywords_filter:
                # At least one keyword must match
                any_match = False
                for keyword in keywords_filter:
                    title_matches = job_title.count(keyword)
                    desc_matches = job_description.count(keyword)
                    total_matches = title_matches + desc_matches
                    
                    if total_matches > 0:
                        any_match = True
                        keyword_match_count += total_matches
                        matched_keywords.append(f"{keyword}({total_matches})")
                
                keywords_match = any_match
            
            # Parse job timestamp
            date_match = True
            if job.get("timestamp"):
                try:
                    job_date = datetime.datetime.fromisoformat(job["timestamp"])
                    if from_date_obj and job_date < from_date_obj:
                        date_match = False
                    if to_date_obj and job_date > to_date_obj:
                        date_match = False
                except (ValueError, TypeError):
                    pass
            
            if title_match and company_match and keywords_match and date_match:
                # Store job with its match score and matched keywords
                job_copy = job.copy()
                job_copy["match_count"] = keyword_match_count
                job_copy["keyword_match_count"] = len(matched_keywords)
                job_copy["matched_keywords"] = ", ".join(matched_keywords[:3])  # Show top 3 matches
                job_matches.append(job_copy)
        
        # Sort by keyword match count if keywords were specified
        if keywords_filter:
            job_matches.sort(key=lambda j: j.get("match_count", 0), reverse=True)
            # Update the current sort to match
            self.current_sort["column"] = "matches"
            self.current_sort["reverse"] = True
            
        self.filtered_jobs = job_matches
        
        # Update results view
        self.update_results_view()
    
    def reset_filters(self):
        """Reset all filters to default values"""
        self.title_var.set("")
        self.company_var.set("")
        self.keywords_var.set("")
        
        # Reset date pickers to empty/None as requested
        try:
            if hasattr(self, 'from_date_picker'):
                self.from_date_picker.set_date(None)
            elif hasattr(self, 'from_date_var'):
                self.from_date_var.set("")
                
            if hasattr(self, 'to_date_picker'):
                self.to_date_picker.set_date(None)
            elif hasattr(self, 'to_date_var'):
                self.to_date_var.set("")
        except:
            pass
            
        self.apply_filters()
    
    def update_results_view(self, resort=True):
        """Update the job results treeview with filtered jobs"""
        # Clear existing items
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        # Add filtered jobs to the treeview
        for job in self.filtered_jobs:
            job_id = job.get("job_id", "")
            title = job.get("title", "")
            company = job.get("company", "")
            
            # Format date for display
            date_display = "Unknown"
            if job.get("timestamp"):
                try:
                    job_date = datetime.datetime.fromisoformat(job["timestamp"])
                    date_display = job_date.strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    pass
            
            self.results_tree.insert("", tk.END, iid=job_id, 
                                   values=(title, company, date_display))
        
        # Update status label with enhanced information
        if self.filtered_jobs:
            avg_matches = sum(job.get("match_count", 0) for job in self.filtered_jobs) / len(self.filtered_jobs)
            self.status_var.set(f"🎯 Found {len(self.filtered_jobs)} jobs (avg {avg_matches:.1f} keyword matches)")
        else:
            self.status_var.set("❌ No jobs found matching current filters")
        
        # Clear job details if no results
        if not self.filtered_jobs:
            self.clear_job_details()
    
    def display_job_details(self, event):
        """Display details of the selected job with enhanced styling"""
        selection = self.results_tree.selection()
        if not selection:
            return
        
        job_id = selection[0]
        
        # Find the job with matching ID
        selected_job = None
        for job in self.filtered_jobs:
            if job.get("job_id") == job_id:
                selected_job = job
                break
        
        if not selected_job:
            return
        
        # Update job detail view with enhanced information
        self.job_title_var.set(selected_job.get("title", "No title available"))
        self.job_company_var.set(f"🏢 {selected_job.get('company', 'Unknown Company')}")
        
        # Format date for display with enhanced styling
        date_display = "Unknown date"
        if selected_job.get("timestamp"):
            try:
                job_date = datetime.datetime.fromisoformat(selected_job["timestamp"])
                date_display = job_date.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                pass
        self.job_date_var.set(f"📅 Posted: {date_display}")
        
        # Show match information if available
        match_count = selected_job.get("match_count", 0)
        matched_keywords = selected_job.get("matched_keywords", "")
        if match_count > 0:
            self.job_match_var.set(f"🎯 {match_count} keyword matches: {matched_keywords}")
        else:
            self.job_match_var.set("")
        
        # Update description text with enhanced formatting
        self.job_description_text.config(state=tk.NORMAL)
        self.job_description_text.delete(1.0, tk.END)
        
        # Format the description text for better readability
        description = selected_job.get("description", "No description available")
        formatted_desc = self.format_description(description)
        
        # Insert the text
        self.job_description_text.insert(tk.END, formatted_desc)
        
        # Enhanced keyword highlighting
        keywords_text = self.keywords_var.get().strip()
        if keywords_text:
            keywords = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]
            for keyword in keywords:
                start_pos = "1.0"
                while True:
                    # Search for keyword (case-insensitive)
                    start_pos = self.job_description_text.search(keyword, start_pos, tk.END, nocase=True)
                    if not start_pos:
                        break
                    
                    end_pos = f"{start_pos}+{len(keyword)}c"
                    self.job_description_text.tag_add("highlight", start_pos, end_pos)
                    start_pos = end_pos
        
        # Remove title highlighting as requested by user
        # Only highlight keywords from search, not job title words
        
        self.job_description_text.config(state=tk.DISABLED)
        
        # Scroll to the top
        self.job_description_text.yview_moveto(0)
    
    def format_description(self, text):
        """Format job description for better readability with enhanced formatting"""
        # Replace multiple newlines with just two
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove "About the job" if it's at the beginning
        text = re.sub(r'^About the job\s*\n', '', text, flags=re.IGNORECASE)
        
        # Add some structure to common sections
        text = re.sub(r'\b(Requirements?:?|Qualifications?:?|Skills?:?)\b', r'\n📋 \1', text, flags=re.IGNORECASE)
        text = re.sub(r'\b(Responsibilities?:?|Duties:?|Role:?)\b', r'\n🎯 \1', text, flags=re.IGNORECASE)
        text = re.sub(r'\b(Benefits?:?|Perks?:?|Compensation:?)\b', r'\n💰 \1', text, flags=re.IGNORECASE)
        text = re.sub(r'\b(About (us|the company):?)\b', r'\n🏢 \1', text, flags=re.IGNORECASE)
        
        return text
    
    def clear_job_details(self):
        """Clear the job details view"""
        self.job_title_var.set("Select a job to view details")
        self.job_company_var.set("")
        self.job_date_var.set("")
        self.job_match_var.set("")
        
        self.job_description_text.config(state=tk.NORMAL)
        self.job_description_text.delete(1.0, tk.END)
        self.job_description_text.insert(1.0, "📋 Select a job from the list to view detailed information here.\n\n🔍 Use the search filters above to narrow down results and find relevant positions.")
        self.job_description_text.config(state=tk.DISABLED)


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    app = JobSearchApp(root)
    root.mainloop() 