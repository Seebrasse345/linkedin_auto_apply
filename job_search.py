import tkinter as tk
from tkinter import ttk, scrolledtext
import json
import os
import datetime
import re
from functools import partial

class JobSearchApp(tk.Toplevel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.title("Job Search")
        self.geometry("1200x800")
        self.minsize(800, 600)
        
        # Load job data
        self.job_data = self.load_job_data()
        self.filtered_jobs = self.job_data.copy()
        
        # For column sorting
        self.current_sort = {
            "column": None,
            "reverse": False
        }
        
        # Setup UI components
        self.create_widgets()
        self.apply_filters()
        
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
        """Create the main UI components"""
        # Main frame with padding
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top section - Search filters
        filter_frame = ttk.LabelFrame(main_frame, text="Search Filters", padding="10")
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Title filter
        ttk.Label(filter_frame, text="Job Title:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.title_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.title_var, width=30).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        self.title_var.trace("w", lambda *args: self.apply_filters())
        
        # Company filter
        ttk.Label(filter_frame, text="Company:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.company_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.company_var, width=30).grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        self.company_var.trace("w", lambda *args: self.apply_filters())
        
        # Keywords filter
        ttk.Label(filter_frame, text="Keywords:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.keywords_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.keywords_var, width=30).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        self.keywords_var.trace("w", lambda *args: self.apply_filters())
        
        # Keywords help text
        ttk.Label(filter_frame, text="(Separate multiple keywords with commas)").grid(row=2, column=1, sticky=tk.W, padx=5)
        
        # Date range filter
        ttk.Label(filter_frame, text="Date Range:").grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        date_frame = ttk.Frame(filter_frame)
        date_frame.grid(row=1, column=3, sticky=tk.W, padx=5, pady=5)
        
        # From date
        ttk.Label(date_frame, text="From:").pack(side=tk.LEFT, padx=(0, 5))
        self.from_date_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.from_date_var, width=10).pack(side=tk.LEFT, padx=(0, 10))
        
        # To date
        ttk.Label(date_frame, text="To:").pack(side=tk.LEFT, padx=(0, 5))
        self.to_date_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.to_date_var, width=10).pack(side=tk.LEFT)
        
        # Date format hint
        ttk.Label(filter_frame, text="(Date format: YYYY-MM-DD)").grid(row=2, column=3, sticky=tk.W, padx=5)
        
        # Apply & Reset buttons
        button_frame = ttk.Frame(filter_frame)
        button_frame.grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        ttk.Button(button_frame, text="Apply Filters", command=self.apply_filters).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Reset Filters", command=self.reset_filters).pack(side=tk.LEFT)
        
        # Status label (showing number of results)
        self.status_var = tk.StringVar()
        ttk.Label(filter_frame, textvariable=self.status_var).grid(row=3, column=1, columnspan=2, sticky=tk.E, padx=5, pady=5)
        
        # Create the paned window for results and details
        paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)
        
        # Left side - Job results list
        results_frame = ttk.LabelFrame(paned_window, text="Job Results", padding="10")
        paned_window.add(results_frame, weight=40)
        
        # Treeview for job results with scrollbar
        self.tree_frame = ttk.Frame(results_frame)
        self.tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        tree_scrollbar = ttk.Scrollbar(self.tree_frame)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Job results treeview
        self.results_tree = ttk.Treeview(
            self.tree_frame,
            columns=("title", "company", "date", "matches"),
            show="headings",
            selectmode="browse",
            height=20
        )
        
        # Configure scrollbar
        tree_scrollbar.config(command=self.results_tree.yview)
        self.results_tree.config(yscrollcommand=tree_scrollbar.set)
        
        # Define columns
        self.results_tree.heading("title", text="Job Title", command=lambda: self.sort_treeview("title", False))
        self.results_tree.heading("company", text="Company", command=lambda: self.sort_treeview("company", False))
        self.results_tree.heading("date", text="Date Posted", command=lambda: self.sort_treeview("date", True))
        self.results_tree.heading("matches", text="Keyword Matches", command=lambda: self.sort_treeview("matches", True))
        
        self.results_tree.column("title", width=250)
        self.results_tree.column("company", width=150)
        self.results_tree.column("date", width=100)
        self.results_tree.column("matches", width=80)
        
        self.results_tree.pack(fill=tk.BOTH, expand=True)
        self.results_tree.bind('<<TreeviewSelect>>', self.display_job_details)
        
        # Right side - Job details
        detail_frame = ttk.LabelFrame(paned_window, text="Job Details", padding="10")
        paned_window.add(detail_frame, weight=60)
        
        # Job header frame
        job_header_frame = ttk.Frame(detail_frame)
        job_header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Job title
        self.job_title_var = tk.StringVar()
        job_title_label = ttk.Label(job_header_frame, textvariable=self.job_title_var, font=("", 16, "bold"))
        job_title_label.pack(anchor=tk.W)
        
        # Company
        self.job_company_var = tk.StringVar()
        job_company_label = ttk.Label(job_header_frame, textvariable=self.job_company_var, font=("", 12))
        job_company_label.pack(anchor=tk.W)
        
        # Date
        self.job_date_var = tk.StringVar()
        job_date_label = ttk.Label(job_header_frame, textvariable=self.job_date_var)
        job_date_label.pack(anchor=tk.W)
        
        # Job description with scrollbar
        self.job_description_text = scrolledtext.ScrolledText(detail_frame, wrap=tk.WORD, width=40, height=20)
        self.job_description_text.pack(fill=tk.BOTH, expand=True)
        self.job_description_text.config(state=tk.DISABLED)
        
        # Configure tag for highlighting keywords
        self.job_description_text.tag_configure("highlight", background="yellow", foreground="black")
    
    def sort_treeview(self, column, is_numeric):
        """Sort treeview contents by a column"""
        # Toggle sort direction if the same column is clicked again
        if self.current_sort["column"] == column:
            self.current_sort["reverse"] = not self.current_sort["reverse"]
        else:
            self.current_sort["column"] = column
            self.current_sort["reverse"] = False
        
        # Update the column headings to show sort direction
        for col in ("title", "company", "date", "matches"):
            # Reset the column heading text
            text = col.capitalize()
            if col == "date":
                text = "Date Posted"
            elif col == "matches":
                text = "Keyword Matches"
                
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
        elif column == "matches":
            # Sort by match count (numeric)
            self.filtered_jobs.sort(key=lambda job: job.get("match_count", 0), reverse=self.current_sort["reverse"])
        
        # Refresh the display without refiltering
        self.update_results_view(resort=False)
    
    def apply_filters(self, *args):
        """Apply filters to job data and update the results view"""
        self.filtered_jobs = []
        
        title_filter = self.title_var.get().lower()
        company_filter = self.company_var.get().lower()
        keywords_text = self.keywords_var.get().strip()
        from_date = self.from_date_var.get()
        to_date = self.to_date_var.get()
        
        # Process keywords - split by commas and trim whitespace
        keywords_filter = [kw.strip().lower() for kw in keywords_text.split(',') if kw.strip()] if keywords_text else []
        
        # Parse dates if provided
        try:
            from_date_obj = datetime.datetime.strptime(from_date, "%Y-%m-%d") if from_date else None
            to_date_obj = datetime.datetime.strptime(to_date, "%Y-%m-%d") if to_date else None
            
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
            
            # Check keywords - now handling multiple keywords
            keywords_match = True
            keyword_match_count = 0
            
            if keywords_filter:
                # At least one keyword must match
                any_match = False
                for keyword in keywords_filter:
                    if keyword in job_title or keyword in job_description:
                        any_match = True
                        # Count keyword appearances in title and description
                        keyword_match_count += job_title.count(keyword) + job_description.count(keyword)
                
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
                # Store job with its match score
                job["match_count"] = keyword_match_count
                job_matches.append(job)
        
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
        self.from_date_var.set("")
        self.to_date_var.set("")
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
            match_count = job.get("match_count", 0)
            
            # Format date for display
            date_display = "Unknown"
            if job.get("timestamp"):
                try:
                    job_date = datetime.datetime.fromisoformat(job["timestamp"])
                    date_display = job_date.strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    pass
            
            # Show match count if keywords were used
            match_display = str(match_count) if match_count > 0 else ""
            
            self.results_tree.insert("", tk.END, iid=job_id, values=(title, company, date_display, match_display))
        
        # Update status label
        self.status_var.set(f"Found {len(self.filtered_jobs)} jobs")
        
        # Clear job details if no results
        if not self.filtered_jobs:
            self.clear_job_details()
    
    def display_job_details(self, event):
        """Display details of the selected job"""
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
        
        # Update job detail view
        self.job_title_var.set(selected_job.get("title", ""))
        self.job_company_var.set(selected_job.get("company", ""))
        
        # Format date for display
        date_display = "Unknown date"
        if selected_job.get("timestamp"):
            try:
                job_date = datetime.datetime.fromisoformat(selected_job["timestamp"])
                date_display = job_date.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                pass
        self.job_date_var.set(f"Posted: {date_display}")
        
        # Update description text
        self.job_description_text.config(state=tk.NORMAL)
        self.job_description_text.delete(1.0, tk.END)
        
        # Format the description text for better readability
        description = selected_job.get("description", "No description available")
        formatted_desc = self.format_description(description)
        
        # Insert the text
        self.job_description_text.insert(tk.END, formatted_desc)
        
        # Highlight keywords if any
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
        
        self.job_description_text.config(state=tk.DISABLED)
        
        # Scroll to the top
        self.job_description_text.yview_moveto(0)
    
    def format_description(self, text):
        """Format job description for better readability"""
        # Replace multiple newlines with just two
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove "About the job" if it's at the beginning
        text = re.sub(r'^About the job\s*\n', '', text)
        
        return text
    
    def clear_job_details(self):
        """Clear the job details view"""
        self.job_title_var.set("")
        self.job_company_var.set("")
        self.job_date_var.set("")
        
        self.job_description_text.config(state=tk.NORMAL)
        self.job_description_text.delete(1.0, tk.END)
        self.job_description_text.config(state=tk.DISABLED)


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    app = JobSearchApp(root)
    root.mainloop() 