"""
Daily Notes Processor for Trilium

This script retrieves notes created in the past day, saves revisions of those notes,
and automatically adds internal links to them.

Usage:
    uv run daily_notes_processor.py [OPTIONS]
    
The script will look for .env files in the following locations (in order):
1. Current directory
2. ~/.trilium-py/.env (if --global flag is used)
3. Custom path specified with --env-file
"""
# /// script
# dependencies = [
#   "trilium-py",
#   "python-dotenv",
#   "click",
#   "rich",
#   "python-dateutil",
# ]
# ///

import os
import sys
import click
import datetime
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import track
from dotenv import load_dotenv
from dateutil import parser as date_parser

from trilium_py.client import ETAPI

console = Console()


def load_env_file(env_file: Path = None, is_global: bool = False) -> tuple:
    """
    Load environment variables from .env file
    
    Args:
        env_file: Path to custom .env file
        is_global: Whether to use global .env file
        
    Returns:
        tuple: (server_url, token, source_path) or (None, None, None) if not found
    """
    source_path = None
    
    # Determine which .env file to load
    if env_file and env_file.exists():
        load_dotenv(env_file)
        source_path = env_file
    elif is_global:
        global_env = Path.home() / '.trilium-py' / '.env'
        if global_env.exists():
            load_dotenv(global_env)
            source_path = global_env
    else:
        local_env = Path.cwd() / '.env'
        if local_env.exists():
            load_dotenv(local_env)
            source_path = local_env
        else:
            return None, None, None
    
    # Get values from environment
    server_url = os.environ.get('TRILIUM_SERVER')
    token = os.environ.get('TRILIUM_TOKEN')
    
    return server_url, token, source_path


def get_notes_created_in_past_day(etapi: ETAPI, days_back: int = 1) -> list:
    """
    Retrieve notes created in the past specified number of days
    
    Args:
        etapi: ETAPI client instance
        days_back: Number of days to look back (default: 1)
        
    Returns:
        list: List of notes created in the specified period
    """
    
    # Search for notes created after the cutoff date
    # Using dateCreated >= cutoff_date
        
    search_query = f"note.dateCreated >= TODAY-{days_back}"
    
    try:
        results = etapi.search_note(search=search_query)
        return results.get('results', [])
    except Exception as e:
        console.print(f"[red]Error searching for notes: {e}[/red]")
        return []


def process_note_revisions(etapi: ETAPI, notes: list, verbose: bool = True) -> dict:
    """
    Save revisions for the given notes
    
    Args:
        etapi: ETAPI client instance
        notes: List of notes to process
        verbose: Whether to show progress information
        
    Returns:
        dict: Processing results with success/failure counts
    """
    results = {
        'total': len(notes),
        'successful': 0,
        'failed': 0,
        'errors': []
    }
    
    if verbose:
        console.print(f"[blue]Processing revisions for {len(notes)} notes...[/blue]")
    
    for note in track(notes, description="Saving revisions..."):
        try:
            note_id = note['noteId']
            success = etapi.save_revision(note_id)
            if success:
                results['successful'] += 1
                if verbose:
                    console.print(f"[green]✓[/green] Revision saved for: {note['title']}")
            else:
                results['failed'] += 1
                results['errors'].append(f"Failed to save revision for {note['title']}")
                if verbose:
                    console.print(f"[red]✗[/red] Failed to save revision for: {note['title']}")
        except Exception as e:
            results['failed'] += 1
            results['errors'].append(f"Error saving revision for {note['title']}: {str(e)}")
            if verbose:
                console.print(f"[red]✗[/red] Error saving revision for {note['title']}: {str(e)}")
    
    return results


def add_internal_links_to_notes(etapi: ETAPI, notes: list, verbose: bool = True) -> dict:
    """
    Automatically add internal links to the given notes
    
    Args:
        etapi: ETAPI client instance
        notes: List of notes to process
        verbose: Whether to show progress information
        
    Returns:
        dict: Processing results with success/failure counts and link counts
    """
    results = {
        'total': len(notes),
        'processed': 0,
        'links_added': 0,
        'errors': []
    }
    
    if verbose:
        console.print(f"[blue]Adding internal links to {len(notes)} notes...[/blue]")
    
    # Get all available notes for linking (excluding protected ones)
    all_notes = etapi.search_note(search="note.title %= '.*' #!ignoreAutoInternalLink")
    all_note_title_list = []
    for x in all_notes['results']:
        if not x['isProtected']:
            title = x['title']
            note_id = x['noteId']
            all_note_title_list.append([title, note_id])
    
    # Process internal links for each note
    for note in track(notes, description="Adding internal links..."):
        try:
            note_id = note['noteId']
            
            # Skip protected notes
            if note['isProtected']:
                if verbose:
                    console.print(f"[yellow]⚠[/yellow] Skipping protected note: {note['title']}")
                continue
            
            # Only process text notes
            if note['type'] != 'text':
                if verbose:
                    console.print(f"[yellow]⚠[/yellow] Skipping non-text note: {note['title']}")
                continue
            
            # Add internal links using the existing auto_create_internal_link functionality
            # but limit to just this specific note
            etapi.auto_create_internal_link(
                target_notes=[note_id],
                verbose=False  # We'll handle our own verbose output
            )
            
            results['processed'] += 1
            if verbose:
                console.print(f"[green]✓[/green] Processed internal links for: {note['title']}")
                
        except Exception as e:
            results['errors'].append(f"Error processing links for {note['title']}: {str(e)}")
            if verbose:
                console.print(f"[red]✗[/red] Error processing links for {note['title']}: {str(e)}")
    
    return results


def display_processing_summary(revision_results: dict, link_results: dict):
    """
    Display a summary of the processing results
    
    Args:
        revision_results: Results from revision processing
        link_results: Results from internal link processing
    """
    console.print("\n" + "="*50)
    console.print("[bold cyan]Processing Summary[/bold cyan]")
    console.print("="*50)
    
    # Revision summary
    table = Table(title="Revision Processing Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Notes", str(revision_results['total']))
    table.add_row("Successful", str(revision_results['successful']))
    table.add_row("Failed", str(revision_results['failed']))
    
    if revision_results['errors']:
        table.add_row("Errors", str(len(revision_results['errors'])))
    
    console.print(table)
    
    # Internal links summary
    table2 = Table(title="Internal Link Processing Results")
    table2.add_column("Metric", style="cyan")
    table2.add_column("Value", style="green")
    
    table2.add_row("Total Notes", str(link_results['total']))
    table2.add_row("Processed", str(link_results['processed']))
    table2.add_row("Errors", str(len(link_results['errors'])))
    
    console.print(table2)
    
    if revision_results['errors'] or link_results['errors']:
        console.print("\n[red]Errors encountered:[/red]")
        for error in revision_results['errors'] + link_results['errors']:
            console.print(f"  • {error}")


@click.command(help="Process daily notes: retrieve recent notes, save revisions, and add internal links")
@click.option("--days-back", "-d", default=1, help="Number of days to look back (default: 1)")
@click.option("--max-notes", "-m", default=100, type=int, help="Maximum number of notes to process (default: 100)")
@click.option("--env-file", "-e", help="Path to .env file with token", 
              type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option("--global", "is_global", is_flag=True, help="Use global ~/.trilium-py/.env file")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Suppress progress output")
def main(days_back: int, max_notes: int, env_file: str, is_global: bool, verbose: bool, quiet: bool):
    """Process daily notes: retrieve notes created in the past day, save revisions, and add internal links."""
    try:
        # Load environment variables
        env_path = Path(env_file) if env_file else None
        server_url, token, source_path = load_env_file(env_path, is_global)
        
        if not server_url or not token:
            console.print(Panel.fit(
                "No Trilium configuration found. Please run get_etapi_token.py first to set up your connection.",
                title="Configuration Not Found",
                border_style="yellow"
            ))
            sys.exit(0)
        
        # Connect to server
        if not quiet:
            console.print(Panel.fit(
                f"[bold]Configuration Source:[/bold] {source_path}\n"
                f"[bold]Server URL:[/bold] {server_url}\n"
                f"[bold]Token:[/bold] {'*' * 8}...{token[-4:] if token else ''}",
                title="Connection Information",
                border_style="blue"
            ))
        
        if not quiet:
            console.print(f"Connecting to Trilium server...")
        etapi = ETAPI(server_url, token)
        
        # Get app info to verify connection
        app_info = etapi.app_info()
        if not quiet:
            console.print(f"[green]✓[/green] Connected to Trilium {app_info['appVersion']}")
        
        # Retrieve notes created in the past day(s)
        if not quiet:
            console.print(f"\n[blue]Retrieving notes created in the past {days_back} day(s)...[/blue]")
        
        recent_notes = get_notes_created_in_past_day(etapi, days_back)
        
        if not recent_notes:
            console.print("[yellow]No notes found in the specified time period.[/yellow]")
            return
        
        # Calculate and display the date range used for selection
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_back)
        cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')
        current_date_str = datetime.datetime.now().strftime('%Y-%m-%d')
        
        if not quiet:
            console.print(f"[dim]Date range: {cutoff_date_str} to {current_date_str}[/dim]")
            console.print(f"[green]Found {len(recent_notes)} notes created in the past {days_back} day(s)[/green]")
        
        # Apply max notes limit if specified
        if max_notes is not None and len(recent_notes) > max_notes:
            recent_notes = recent_notes[:max_notes]
            if not quiet:
                console.print(f"[yellow]Limited to processing {max_notes} notes (out of {len(recent_notes)} total)[/yellow]")
        
        # Process revisions
        revision_results = process_note_revisions(etapi, recent_notes, verbose and not quiet)
        
        # Add internal links
        link_results = add_internal_links_to_notes(etapi, recent_notes, verbose and not quiet)
        
        # Display summary
        if not quiet:
            display_processing_summary(revision_results, link_results)
        
        console.print("\n[bold green]✓ Daily notes processing completed successfully![/bold green]")
        
    except Exception as e:
        console.print(Panel.fit(
            f"[bold red]✗ Processing failed: {str(e)}[/bold red]\n\n"
            "Please check:\n"
            "- Server URL is correct\n"
            "- Token is valid\n"
            "- Trilium server is running and accessible",
            title="Processing Failed",
            border_style="red"
        ))
        sys.exit(1)


if __name__ == "__main__":
    main()
