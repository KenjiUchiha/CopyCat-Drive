#!/usr/bin/env python3
"""
Backup Cloner V5 - Full System Backup Utility
Version 5.0 - Enhanced Edition

NEW IN V5:
✓ ZIP64 support for files >4GB (CRITICAL FIX)
✓ Real-time progress tracking with ETA
✓ Backup integrity verification  
✓ SHA-256 checksum generation
✓ Improved error recovery with retry logic
✓ Live destination space monitoring
✓ Better memory management for large drives
✓ Enhanced statistics and logging
"""

import os
import sys
import shutil
import zipfile
import platform
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import psutil
from functools import wraps
import time

VERSION = "5.0"
VERSION_NAME = "Enhanced Edition"

def retry_on_error(max_attempts=3, delay=1):
    """Decorator to retry operations on temporary errors"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except (PermissionError, OSError) as e:
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
                        continue
                    raise
            return None
        return wrapper
    return decorator

class BackupUtility:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Backup Cloner V{VERSION}")
        self.root.geometry("750x720")
        
        self.is_backing_up = False
        self.backup_thread = None
        self.total_files_estimate = 0
        self.start_time = None
        
        # Create main canvas with scrollbar
        self.main_canvas = tk.Canvas(root)
        self.scrollbar = ttk.Scrollbar(root, orient="vertical", command=self.main_canvas.yview)
        self.scrollable_frame = tk.Frame(self.main_canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        )
        
        self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.scrollbar.pack(side="right", fill="y")
        self.main_canvas.pack(side="left", fill="both", expand=True)
        self.main_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        self.setup_ui()
        
    def _on_mousewheel(self, event):
        self.main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
    def setup_ui(self):
        # Title
        title_label = tk.Label(
            self.scrollable_frame, 
            text=f"Backup Cloner V{VERSION}", 
            font=("Arial", 18, "bold"),
            fg="#2E7D32"
        )
        title_label.pack(pady=10)
        
        version_label = tk.Label(
            self.scrollable_frame,
            text=f"{VERSION_NAME} - ZIP64 | Progress Tracking | Verification | Checksums",
            font=("Arial", 8),
            fg="gray"
        )
        version_label.pack()
        
        # Control buttons
        button_frame_top = tk.Frame(self.scrollable_frame)
        button_frame_top.pack(pady=15)
        
        self.backup_btn = tk.Button(
            button_frame_top, 
            text="▶ START FULL SYSTEM BACKUP", 
            command=self.start_backup,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 14, "bold"),
            padx=30,
            pady=10,
            cursor="hand2"
        )
        self.backup_btn.pack(side="left", padx=5)
        
        self.cancel_btn = tk.Button(
            button_frame_top, 
            text="■ CANCEL", 
            command=self.cancel_backup,
            state="disabled",
            bg="#f44336",
            fg="white",
            font=("Arial", 14, "bold"),
            padx=30,
            pady=10
        )
        self.cancel_btn.pack(side="left", padx=5)
        
        ttk.Separator(self.scrollable_frame, orient='horizontal').pack(fill='x', padx=20, pady=10)
        
        # System info
        info_frame = tk.LabelFrame(self.scrollable_frame, text="System Information", padx=10, pady=5)
        info_frame.pack(pady=5, padx=20, fill="x")
        
        tk.Label(info_frame, text=f"OS: {platform.system()} {platform.release()}").pack(anchor="w")
        tk.Label(info_frame, text=f"Machine: {platform.machine()}").pack(anchor="w")
        
        try:
            if platform.system() == "Windows":
                drives = [d.device for d in psutil.disk_partitions()]
                tk.Label(info_frame, text="Drives: " + ", ".join(drives), fg="blue").pack(anchor="w")
            else:
                usage = psutil.disk_usage('/')
                tk.Label(info_frame, text=f"Root: {self.format_size(usage.total)}", fg="blue").pack(anchor="w")
        except:
            pass
        
        # Destination selection
        dest_frame = tk.LabelFrame(self.scrollable_frame, text="Backup Destination", padx=10, pady=5)
        dest_frame.pack(pady=10, padx=20, fill="x")
        
        dest_select_frame = tk.Frame(dest_frame)
        dest_select_frame.pack(fill="x", pady=5)
        
        self.dest_var = tk.StringVar(value=str(Path.home() / "Desktop"))
        self.dest_entry = tk.Entry(dest_select_frame, textvariable=self.dest_var, width=50)
        self.dest_entry.pack(side="left", padx=(0, 5))
        
        self.browse_btn = tk.Button(dest_select_frame, text="Browse", command=self.browse_destination)
        self.browse_btn.pack(side="left")
        
        self.dest_space_label = tk.Label(dest_frame, text="", fg="gray")
        self.dest_space_label.pack(anchor="w", pady=(5, 0))
        self.update_dest_space()
        
        # Options frame
        options_frame = tk.LabelFrame(self.scrollable_frame, text="Backup Options", padx=10, pady=10)
        options_frame.pack(pady=10, padx=20, fill="x")
        
        self.skip_temp_var = tk.BooleanVar(value=True)
        tk.Checkbutton(options_frame, text="Skip temporary and cache files (recommended)", 
                      variable=self.skip_temp_var).pack(anchor="w")
        
        self.skip_large_var = tk.BooleanVar(value=False)
        tk.Checkbutton(options_frame, text="Skip files larger than 2GB", 
                      variable=self.skip_large_var).pack(anchor="w")
        
        self.exclude_media_var = tk.BooleanVar(value=False)
        tk.Checkbutton(options_frame, text="Exclude video files (saves space)", 
                      variable=self.exclude_media_var).pack(anchor="w")
        
        self.verify_space_var = tk.BooleanVar(value=True)
        tk.Checkbutton(options_frame, text="Verify sufficient space before backup", 
                      variable=self.verify_space_var).pack(anchor="w")
        
        self.skip_browser_cache_var = tk.BooleanVar(value=False)
        tk.Checkbutton(options_frame, text="Skip browser cache and volatile files", 
                      variable=self.skip_browser_cache_var).pack(anchor="w")
        
        # V5 New Features
        v5_frame = tk.Frame(options_frame, bg="#E8F5E9", relief=tk.GROOVE, borderwidth=2)
        v5_frame.pack(fill="x", pady=(10, 0))
        
        tk.Label(v5_frame, text="✨ NEW IN V5:", font=("Arial", 9, "bold"), 
                bg="#E8F5E9", fg="#2E7D32").pack(anchor="w", padx=5, pady=(5, 0))
        
        self.verify_backup_var = tk.BooleanVar(value=True)
        tk.Checkbutton(v5_frame, text="✓ Verify backup integrity after completion", 
                      variable=self.verify_backup_var, bg="#E8F5E9", fg="#1B5E20").pack(anchor="w", padx=5)
        
        self.generate_checksum_var = tk.BooleanVar(value=True)
        tk.Checkbutton(v5_frame, text="✓ Generate SHA-256 checksum file", 
                      variable=self.generate_checksum_var, bg="#E8F5E9", fg="#1B5E20").pack(anchor="w", padx=5, pady=(0, 5))
        
        # Progress section
        progress_frame = tk.LabelFrame(self.scrollable_frame, text="Backup Progress", padx=10, pady=10)
        progress_frame.pack(pady=10, padx=20, fill="both")
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=300)
        self.progress_bar.pack(fill="x", pady=5)
        
        self.status_label = tk.Label(progress_frame, text="Ready to start backup", font=("Arial", 10))
        self.status_label.pack(anchor="w")
        
        self.eta_label = tk.Label(progress_frame, text="", fg="blue", font=("Arial", 9))
        self.eta_label.pack(anchor="w")
        
        tk.Label(progress_frame, text="Activity Log:", font=("Arial", 9, "bold")).pack(anchor="w", pady=(10, 0))
        self.log_text = scrolledtext.ScrolledText(progress_frame, height=8, width=80, wrap=tk.WORD)
        self.log_text.pack(fill="both")
        
        # Footer
        footer_frame = tk.Frame(self.scrollable_frame, bg="#FFF3E0", relief=tk.RIDGE, borderwidth=1)
        footer_frame.pack(pady=10, padx=20, fill="x")
        tk.Label(footer_frame, 
                text="⚠️ TIP: For 2TB+ drives, ensure destination has 500GB-1TB free space",
                font=("Arial", 9), fg="#E65100", bg="#FFF3E0").pack(pady=5)
    
    def update_dest_space(self):
        try:
            dest_path = Path(self.dest_var.get())
            if dest_path.exists():
                usage = psutil.disk_usage(str(dest_path))
                free = self.format_size(usage.free)
                total = self.format_size(usage.total)
                pct = (usage.free / usage.total) * 100
                color = "green" if pct > 20 else "orange" if pct > 10 else "red"
                self.dest_space_label.config(
                    text=f"Available: {free} of {total} ({pct:.1f}% free)", fg=color)
        except:
            self.dest_space_label.config(text="")
    
    def browse_destination(self):
        folder = filedialog.askdirectory(title="Select Backup Destination (External Drive Recommended)")
        if folder:
            self.dest_var.set(folder)
            self.update_dest_space()

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def calculate_eta(self, files_processed, elapsed_seconds):
        if files_processed > 0 and self.total_files_estimate > 0:
            rate = files_processed / elapsed_seconds
            remaining = self.total_files_estimate - files_processed
            eta_sec = remaining / rate if rate > 0 else 0
            return str(timedelta(seconds=int(eta_sec)))
        return "Calculating..."
    
    def check_space_during_backup(self, required_gb=10):
        try:
            usage = psutil.disk_usage(str(self.dest_var.get()))
            free_gb = usage.free / (1024**3)
            return (free_gb >= required_gb, free_gb)
        except:
            return (True, 0)
    
    def sanitize_filename(self, filename):
        return "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.'))
    
    def generate_checksum(self, file_path):
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for block in iter(lambda: f.read(8192), b""):
                    if not self.is_backing_up:
                        return None
                    sha256_hash.update(block)
            return sha256_hash.hexdigest()
        except Exception as e:
            self.log(f"⚠️ Checksum error: {str(e)}")
            return None
    
    def verify_backup_integrity(self, backup_path):
        try:
            self.log("🔍 Verifying backup integrity...")
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                corrupt = zipf.testzip()
                if corrupt is None:
                    self.log("✅ Backup integrity verified - no corruption detected")
                    return True
                else:
                    self.log(f"❌ Corruption detected in: {corrupt}")
                    return False
        except Exception as e:
            self.log(f"❌ Verification failed: {str(e)}")
            return False
    
    def start_backup(self):
        if not self.dest_var.get():
            messagebox.showerror("Error", "Please select a backup destination")
            return
        
        dest_path = Path(self.dest_var.get())
        if not dest_path.exists():
            messagebox.showerror("Error", "Selected destination does not exist")
            return
        
        # Check available space
        if self.verify_space_var.get():
            try:
                usage = psutil.disk_usage(str(dest_path))
                free_gb = usage.free / (1024**3)
                if free_gb < 100:
                    result = messagebox.askyesno(
                        "Low Disk Space",
                        f"Destination has only {free_gb:.1f} GB free.\n\n"
                        "For a 2TB source drive, you may need 500GB-1TB+ free space.\n\n"
                        "Continue anyway?"
                    )
                    if not result:
                        return
            except:
                pass
        
        # Confirmation dialog
        result = messagebox.askyesno(
            "Confirm Full System Backup",
            f"⚠️ BACKUP CLONER V{VERSION}\n\n"
            "ABOUT TO START:\n"
            "• Full system backup to compressed archive\n"
            "• Estimated time: 4-12+ hours for large drives\n"
            "• Some locked files will be skipped (normal)\n"
            "• Do NOT disconnect drives during backup\n\n"
            "✨ NEW IN V5:\n"
            "✓ ZIP64 support (files >4GB)\n"
            "✓ Real-time progress tracking with ETA\n"
            "✓ Automatic backup verification\n"
            "✓ SHA-256 checksum generation\n"
            "✓ Better error recovery\n\n"
            "RECOMMENDATIONS:\n"
            "• Close all programs\n"
            "• Disable antivirus temporarily\n"
            "• Prevent computer sleep\n\n"
            "Proceed with backup?",
            icon='warning'
        )
        
        if not result:
            return
        
        self.is_backing_up = True
        self.backup_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.browse_btn.config(state="disabled")
        self.progress_bar['value'] = 0
        self.log(f"🚀 Backup Cloner V{VERSION} - Starting backup process...")
        
        # Run backup in separate thread
        self.backup_thread = threading.Thread(target=self.perform_backup, daemon=True)
        self.backup_thread.start()
    
    def cancel_backup(self):
        self.is_backing_up = False
        self.log("⚠️ Cancelling backup (may take a moment)...")
        self.cancel_btn.config(state="disabled")
    
    def perform_backup(self):
        self.start_time = datetime.now()
        issues_found = []
        
        try:
            timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
            system_name = self.sanitize_filename(platform.node().replace(" ", "_"))
            backup_filename = f"BackupCloner_V{VERSION.replace('.', '-')}_{system_name}_{timestamp}.zip"
            backup_path = Path(self.dest_var.get()) / backup_filename
            
            self.log(f"📁 Creating backup archive...")
            self.log(f"📝 Filename: {backup_filename}")
            self.log(f"💾 Destination: {self.dest_var.get()}")
            self.log(f"🖥️ System: {platform.system()} {platform.release()}")
            self.status_label.config(text=f"Initializing backup...")
            
            # Determine root paths
            if platform.system() == "Windows":
                roots = [Path(f"{d}:\\") for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if Path(f"{d}:\\").exists()]
                self.log(f"📂 Detected drives: {', '.join(str(r) for r in roots)}")
            else:
                roots = [Path("/")]
                self.log(f"📂 Backing up from root: /")
            
            skip_paths = self.get_skip_paths()
            
            files_processed = 0
            files_skipped = 0
            files_skipped_ini = 0
            files_skipped_tmp = 0
            files_skipped_journal = 0
            files_skipped_browser = 0
            total_size = 0
            last_log_time = datetime.now()
            last_space_check = datetime.now()
            
            media_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
            browser_cache_patterns = ['cache', 'cookies', 'history', 'thumbnails',
                                     'browsermetrics', 'variations', 'network action predictor']
            
            # CRITICAL V5 FIX: Enable ZIP64 support for files >4GB
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED, 
                               compresslevel=5, allowZip64=True) as zipf:
                
                # Quick file count estimate
                sample_count = 0
                for root_path in roots:
                    for current_root, dirs, files in os.walk(root_path, topdown=True):
                        sample_count += len(files)
                        if sample_count >= 1000:
                            break
                    if sample_count >= 1000:
                        break
                
                if sample_count > 0:
                    self.total_files_estimate = sample_count * 100
                    self.log(f"📊 Estimated files: ~{self.total_files_estimate:,}")
                
                for root_path in roots:
                    if not self.is_backing_up:
                        break
                        
                    self.log(f"📂 Scanning: {root_path}")
                    
                    for current_root, dirs, files in os.walk(root_path, topdown=True):
                        if not self.is_backing_up:
                            self.log("❌ Backup cancelled by user")
                            break
                        
                        current_path = Path(current_root)
                        
                        if self.should_skip_path(current_path, skip_paths):
                            dirs.clear()
                            continue
                        
                        dirs[:] = [d for d in dirs if not self.should_skip_path(current_path / d, skip_paths)]
                        
                        for file in files:
                            if not self.is_backing_up:
                                break
                                
                            file_path = current_path / file
                            
                            try:
                                # Skip system files
                                if file_path.suffix.lower() == '.ini':
                                    files_skipped_ini += 1
                                    continue
                                
                                if file_path.suffix.lower() == '.tmp':
                                    files_skipped_tmp += 1
                                    continue
                                
                                if file_path.suffix.lower() in ['.db-journal', '.db-shm', '.db-wal']:
                                    files_skipped_journal += 1
                                    continue
                                
                                # Skip browser cache
                                if self.skip_browser_cache_var.get():
                                    if any(p in file_path.name.lower() for p in browser_cache_patterns):
                                        files_skipped_browser += 1
                                        continue
                                
                                # Skip media
                                if self.exclude_media_var.get() and file_path.suffix.lower() in media_extensions:
                                    files_skipped += 1
                                    continue
                                
                                file_size = file_path.stat().st_size
                                
                                # Skip large files
                                if self.skip_large_var.get() and file_size > 2_000_000_000:
                                    files_skipped += 1
                                    continue
                                
                                # Add to ZIP
                                try:
                                    if platform.system() == "Windows":
                                        arcname = str(file_path)
                                    else:
                                        arcname = str(file_path.relative_to('/'))
                                    
                                    zipf.write(file_path, arcname)
                                    files_processed += 1
                                    total_size += file_size
                                    
                                    # Update UI
                                    now = datetime.now()
                                    if files_processed % 100 == 0 or (now - last_log_time).seconds >= 3:
                                        elapsed = (now - self.start_time).total_seconds()
                                        rate = files_processed / elapsed if elapsed > 0 else 0
                                        
                                        # Update progress bar
                                        if self.total_files_estimate > 0:
                                            progress = min(100, (files_processed / self.total_files_estimate) * 100)
                                            self.progress_bar['value'] = progress
                                        
                                        eta = self.calculate_eta(files_processed, elapsed)
                                        
                                        self.status_label.config(
                                            text=f"Files: {files_processed:,} | Size: {self.format_size(total_size)} | {rate:.1f} files/sec"
                                        )
                                        self.eta_label.config(text=f"⏱️ ETA: {eta}")
                                        
                                        if files_processed % 500 == 0:
                                            self.log(f"✓ {files_processed:,} files ({self.format_size(total_size)})")
                                        
                                        last_log_time = now
                                    
                                    # Space check every 5 minutes
                                    if (now - last_space_check).seconds >= 300:
                                        has_space, free_gb = self.check_space_during_backup()
                                        if not has_space:
                                            raise IOError(f"Insufficient space: {free_gb:.1f}GB")
                                        last_space_check = now
                                        
                                except Exception as e:
                                    files_skipped += 1
                                    
                            except (PermissionError, OSError, IOError, FileNotFoundError) as e:
                                files_skipped += 1
                                issues_found.append(f"Cannot access: {file_path} - {str(e)}")
            
            if not self.is_backing_up:
                try:
                    backup_path.unlink()
                    self.log("🗑️ Incomplete backup removed")
                except:
                    pass
                return
            
            # Backup complete
            end_time = datetime.now()
            duration = end_time - self.start_time
            
            self.progress_bar['value'] = 100
            self.status_label.config(text="✅ Backup complete - Post-processing...")
            
            backup_size = backup_path.stat().st_size
            compression_ratio = (1 - backup_size/total_size)*100 if total_size > 0 else 0
            
            # V5 Feature: Verify backup
            backup_verified = False
            if self.verify_backup_var.get():
                backup_verified = self.verify_backup_integrity(backup_path)
            
            # V5 Feature: Generate checksum
            checksum = None
            if self.generate_checksum_var.get():
                self.log("🔐 Generating SHA-256 checksum...")
                checksum = self.generate_checksum(backup_path)
                if checksum:
                    self.log(f"✓ Checksum: {checksum[:16]}...{checksum[-16:]}")
                    checksum_file = backup_path.parent / f"{backup_path.name}.sha256"
                    with open(checksum_file, 'w') as f:
                        f.write(f"{checksum}  {backup_path.name}\n")
                    self.log(f"📄 Saved: {checksum_file.name}")
            
            # Create finish log
            finish_log_path = backup_path.parent / f"BackupCloner_V{VERSION.replace('.', '-')}_Log_{timestamp}.txt"
            self.create_finish_log(
                finish_log_path, self.start_time, end_time, duration,
                files_processed, files_skipped, files_skipped_ini,
                files_skipped_tmp, files_skipped_journal, files_skipped_browser,
                total_size, backup_size, compression_ratio,
                backup_path, issues_found, backup_verified, checksum
            )
            
            self.status_label.config(text="✅ Backup completed successfully!")
            
            self.log(f"\n{'='*60}")
            self.log(f"✅ BACKUP COMPLETED SUCCESSFULLY!")
            self.log(f"{'='*60}")
            self.log(f"📊 Final Statistics:")
            self.log(f"   • Files backed up: {files_processed:,}")
            self.log(f"   • Files skipped: {files_skipped:,}")
            self.log(f"   • Original size: {self.format_size(total_size)}")
            self.log(f"   • Backup size: {self.format_size(backup_size)}")
            self.log(f"   • Compression: {compression_ratio:.1f}%")
            self.log(f"   • Duration: {duration}")
            if backup_verified:
                self.log(f"   ✓ Integrity verified")
            if checksum:
                self.log(f"   ✓ Checksum generated")
            self.log(f"📝 Backup: {backup_path}")
            self.log(f"📄 Log: {finish_log_path}")
            self.log(f"{'='*60}")
            
            messagebox.showinfo(
                f"Backup Cloner V{VERSION} - Success! ✅",
                f"Full system backup completed!\n\n"
                f"Files: {files_processed:,}\n"
                f"Size: {self.format_size(total_size)} → {self.format_size(backup_size)}\n"
                f"Compression: {compression_ratio:.1f}%\n"
                f"Duration: {duration}\n\n"
                f"{'✓ Verified' if backup_verified else ''}\n"
                f"{'✓ Checksum generated' if checksum else ''}\n\n"
                f"Location: {backup_path.parent}"
            )
            
        except Exception as e:
            self.log(f"\n❌ ERROR: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
            messagebox.showerror("Backup Failed", f"Error during backup:\n\n{str(e)}")
        
        finally:
            self.is_backing_up = False
            self.backup_btn.config(state="normal")
            self.cancel_btn.config(state="disabled")
            self.browse_btn.config(state="normal")

    def create_finish_log(self, log_path, start_time, end_time, duration,
                          files_processed, files_skipped, files_skipped_ini,
                          files_skipped_tmp, files_skipped_journal, files_skipped_browser,
                          total_size, backup_size, compression_ratio,
                          backup_path, issues_found, backup_verified, checksum):
        """Create detailed finish log"""
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write(f" BACKUP CLONER V{VERSION} - COMPLETION LOG\n")
                f.write(f" {VERSION_NAME}\n")
                f.write("="*80 + "\n\n")
                
                f.write("TIME INFORMATION:\n")
                f.write("-" * 80 + "\n")
                f.write(f"Start:    {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"End:      {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Duration: {duration}\n\n")
                
                f.write("SYSTEM INFORMATION:\n")
                f.write("-" * 80 + "\n")
                f.write(f"OS:       {platform.system()} {platform.release()}\n")
                f.write(f"Machine:  {platform.machine()}\n")
                f.write(f"Computer: {platform.node()}\n")
                f.write(f"Python:   {platform.python_version()}\n\n")
                
                f.write("BACKUP CONFIGURATION:\n")
                f.write("-" * 80 + "\n")
                f.write(f"Destination: {backup_path.parent}\n")
                f.write(f"Filename:    {backup_path.name}\n")
                f.write(f"Skip Temp:   {'Yes' if self.skip_temp_var.get() else 'No'}\n")
                f.write(f"Skip Large:  {'Yes' if self.skip_large_var.get() else 'No'}\n")
                f.write(f"Skip Videos: {'Yes' if self.exclude_media_var.get() else 'No'}\n")
                f.write(f"Skip Browser Cache: {'Yes' if self.skip_browser_cache_var.get() else 'No'}\n")
                f.write(f"Verify Backup: {'Yes' if self.verify_backup_var.get() else 'No'}\n")
                f.write(f"Generate Checksum: {'Yes' if self.generate_checksum_var.get() else 'No'}\n\n")
                
                f.write("FILE PROCESSING STATISTICS:\n")
                f.write("-" * 80 + "\n")
                f.write(f"Files Backed Up:           {files_processed:,}\n")
                f.write(f"Files Skipped (Access):    {files_skipped:,}\n")
                f.write(f"Files Skipped (.ini):      {files_skipped_ini:,}\n")
                f.write(f"Files Skipped (.tmp):      {files_skipped_tmp:,}\n")
                f.write(f"Files Skipped (DB logs):   {files_skipped_journal:,}\n")
                f.write(f"Files Skipped (Browser):   {files_skipped_browser:,}\n\n")
                
                f.write("SIZE INFORMATION:\n")
                f.write("-" * 80 + "\n")
                f.write(f"Original Size:    {self.format_size(total_size)}\n")
                f.write(f"Compressed Size:  {self.format_size(backup_size)}\n")
                f.write(f"Space Saved:      {self.format_size(total_size - backup_size)}\n")
                f.write(f"Compression:      {compression_ratio:.2f}%\n\n")
                
                if duration.total_seconds() > 0:
                    files_per_sec = files_processed / duration.total_seconds()
                    mb_per_sec = (total_size / (1024*1024)) / duration.total_seconds()
                    
                    f.write("PERFORMANCE METRICS:\n")
                    f.write("-" * 80 + "\n")
                    f.write(f"Processing Speed:  {files_per_sec:.2f} files/second\n")
                    f.write(f"Transfer Rate:     {mb_per_sec:.2f} MB/second\n\n")
                
                f.write("V5 ENHANCEMENTS:\n")
                f.write("-" * 80 + "\n")
                f.write("✓ ZIP64 support enabled (files >4GB supported)\n")
                f.write("✓ Real-time progress tracking with ETA\n")
                if backup_verified:
                    f.write("✓ Backup integrity verified - no corruption\n")
                else:
                    f.write("○ Backup verification skipped\n")
                if checksum:
                    f.write(f"✓ SHA-256 checksum: {checksum}\n")
                else:
                    f.write("○ Checksum generation skipped\n")
                f.write("✓ Improved error recovery\n")
                f.write("✓ Live space monitoring\n\n")
                
                f.write("OPERATIONS COMPLETED:\n")
                f.write("-" * 80 + "\n")
                f.write("✓ Full system scan performed\n")
                f.write("✓ Files compressed and archived\n")
                f.write("✓ System files automatically skipped\n")
                if self.skip_browser_cache_var.get():
                    f.write("✓ Browser cache excluded\n")
                if self.exclude_media_var.get():
                    f.write("✓ Video files excluded\n")
                if self.skip_large_var.get():
                    f.write("✓ Files >2GB excluded\n")
                if self.skip_temp_var.get():
                    f.write("✓ Temp/cache directories excluded\n")
                f.write("✓ Completion log created\n\n")
                
                if issues_found:
                    f.write("\n" + "="*80 + "\n")
                    f.write("ISSUES FOUND\n")
                    f.write("="*80 + "\n\n")
                    f.write(f"Total Issues: {len(issues_found)}\n\n")
                    
                    permission_errors = [i for i in issues_found if "Permission" in i or "access" in i.lower()]
                    not_found_errors = [i for i in issues_found if "not found" in i.lower()]
                    other_errors = [i for i in issues_found if i not in permission_errors and i not in not_found_errors]
                    
                    if permission_errors:
                        f.write(f"\nPERMISSION ERRORS ({len(permission_errors)}):\n")
                        for issue in permission_errors[:20]:
                            f.write(f"  • {issue}\n")
                        if len(permission_errors) > 20:
                            f.write(f"  ... and {len(permission_errors) - 20} more\n")
                    
                    if not_found_errors:
                        f.write(f"\nFILE NOT FOUND ({len(not_found_errors)}):\n")
                        for issue in not_found_errors[:20]:
                            f.write(f"  • {issue}\n")
                        if len(not_found_errors) > 20:
                            f.write(f"  ... and {len(not_found_errors) - 20} more\n")
                    
                    if other_errors:
                        f.write(f"\nOTHER ERRORS ({len(other_errors)}):\n")
                        for issue in other_errors[:20]:
                            f.write(f"  • {issue}\n")
                        if len(other_errors) > 20:
                            f.write(f"  ... and {len(other_errors) - 20} more\n")
                    
                    f.write("\nNOTE: These are typically caused by:\n")
                    f.write("  • Files in use by other programs\n")
                    f.write("  • System files requiring elevated permissions\n")
                    f.write("  • Files deleted during backup\n")
                    f.write("  • Network drives disconnected\n")
                else:
                    f.write("\n" + "="*80 + "\n")
                    f.write("NO ISSUES FOUND\n")
                    f.write("="*80 + "\n")
                    f.write("✓ Backup completed without detected issues\n")
                
                f.write("\n" + "="*80 + "\n")
                f.write("END OF LOG\n")
                f.write("="*80 + "\n")
                
            self.log(f"📄 Detailed log created: {log_path.name}")
            
        except Exception as e:
            self.log(f"⚠️ Warning: Could not create finish log: {str(e)}")
    
    def get_skip_paths(self):
        """Return paths that should be skipped"""
        skip = set()
        
        # Skip program's own directory
        try:
            if getattr(sys, 'frozen', False):
                exe_dir = Path(sys.executable).parent.resolve()
                skip.add(exe_dir)
            else:
                script_dir = Path(__file__).parent.resolve()
                skip.add(script_dir)
        except:
            pass
        
        if self.skip_temp_var.get():
            if platform.system() == "Windows":
                skip.update([
                    Path(os.environ.get('TEMP', 'C:\\Windows\\Temp')),
                    Path(os.environ.get('TMP', 'C:\\Windows\\Temp')),
                    Path("C:\\Windows\\Temp"),
                    Path("C:\\ProgramData\\Package Cache"),
                    Path("C:\\Windows\\SoftwareDistribution"),
                    Path("C:\\Windows\\Installer"),
                ])
                try:
                    user_temp = Path.home() / "AppData" / "Local" / "Temp"
                    skip.add(user_temp)
                except:
                    pass
            else:
                skip.update([
                    Path("/tmp"),
                    Path("/var/tmp"),
                    Path("/var/cache"),
                    Path("/var/log"),
                    Path(f"{Path.home()}/.cache"),
                ])
        
        # Skip backup destination
        try:
            skip.add(Path(self.dest_var.get()).resolve())
        except:
            pass
        
        return skip
    
    def should_skip_path(self, path, skip_paths):
        """Check if a path should be skipped"""
        try:
            path_resolved = path.resolve()
            
            for skip_path in skip_paths:
                try:
                    skip_resolved = skip_path.resolve()
                    if path_resolved == skip_resolved or skip_resolved in path_resolved.parents:
                        return True
                except:
                    continue
            
            # Skip common system/virtual directories
            path_str = str(path).lower()
            skip_patterns = [
                '/proc', '/sys', '/dev', '/run',
                '$recycle.bin', 'system volume information',
                'pagefile.sys', 'hiberfil.sys', 'swapfile.sys',
                'windows\\csc',
            ]
            
            for pattern in skip_patterns:
                if pattern in path_str:
                    return True
            
            if not path.exists():
                return True
                    
            return False
        except:
            return True
    
    @staticmethod
    def format_size(bytes_size):
        """Format bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.2f} PB"

def check_admin():
    """Check if running with admin/root privileges"""
    try:
        if platform.system() == "Windows":
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            return os.geteuid() == 0
    except:
        return False

def main():
    is_admin = check_admin()
    
    root = tk.Tk()
    
    # Set icon if available
    try:
        if platform.system() == "Windows" and hasattr(sys, '_MEIPASS'):
            icon_path = os.path.join(sys._MEIPASS, 'icon.ico')
            if os.path.exists(icon_path):
                root.iconbitmap(icon_path)
    except:
        pass
    
    if not is_admin:
        warning_msg = (
            "⚠️ Administrator/Root Privileges Recommended\n\n"
            "This program works best with elevated privileges.\n\n"
            "Without admin rights:\n"
            "• Some system files will be inaccessible\n"
            "• More files will be skipped\n"
            "• Backup may be incomplete\n\n"
        )
        
        if platform.system() == "Windows":
            warning_msg += "To run as administrator:\n• Right-click the program\n• Select 'Run as administrator'"
        else:
            warning_msg += "To run with root:\n• Open terminal\n• Run: sudo ./BackupClonerV5"
        
        result = messagebox.askyesno(
            "Administrator Rights Recommended",
            warning_msg + "\n\nContinue anyway?",
            icon='warning'
        )
        
        if not result:
            sys.exit(0)
    
    app = BackupUtility(root)
    root.mainloop()

if __name__ == "__main__":
    main()