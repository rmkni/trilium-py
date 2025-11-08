"""
Daily Notes Processor for Trilium

This script retrieves notes created in the past day, saves revisions of those notes,
adds internal links to them, and processes notes with #link labels by fetching
URL content using newspaper3k.

For notes with #link labels, the script will:
- Extract URLs from the note content
- Fetch article content using newspaper3k
- Add a #url="insert url here" tag to the note
- Append the fetched content to the note

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
#   "newspaper3k",
#   "requests",
#   "lxml-html-clean",
#   "readability-lxml",
#   "beautifulsoup4",
# ]
# ///


import os
import sys
import click
import datetime
import re
import urllib.parse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import track
from dotenv import load_dotenv
from dateutil import parser as date_parser
import newspaper
from newspaper import Article
from newspaper.article import ArticleException
from bs4 import BeautifulSoup
import html as html_module

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


def get_notes_modified_in_past_days(etapi: ETAPI, days_back: int = 1) -> list:
    """
    Retrieve notes modified in the past specified number of days
    
    Args:
        etapi: ETAPI client instance
        days_back: Number of days to look back (default: 1)
        
    Returns:
        list: List of notes modified in the specified period
    """
    
    # Search for notes modified after the cutoff date
    # Using dateModified >= cutoff_date
        
    search_query = f"note.dateModified >= TODAY-{days_back}"
    
    try:
        results = etapi.search_note(search=search_query)
        return results.get('results', [])
    except Exception as e:
        console.print(f"[red]Error searching for modified notes: {e}[/red]")
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
            
            # Skip notes with title starting with "Lien inclus : "
            if note['title'].startswith("Lien inclus : "):
                if verbose:
                    console.print(f"[yellow]⚠[/yellow] Skipping 'Lien inclus' note: {note['title']}")
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


def extract_urls_from_text(text: str) -> list:
    """
    Extract URLs from text content
    
    Args:
        text: Text content to search for URLs
        
    Returns:
        list: List of found URLs
    """
    # Check if the text is a URL
    text = text.strip()
    if text.startswith('http://') or text.startswith('https://'):
        return [text]
    
    return []


def extract_article_title_from_url(url: str) -> str:
    """
    Extract article title from a URL using newspaper3k
    
    Args:
        url: URL to extract title from
        
    Returns:
        str: Article title or None if extraction fails
    """
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.title or None
    except Exception as e:
        console.print(f"[yellow]Warning: Could not extract title from {url}: {str(e)}[/yellow]")
        return None


def extract_article_title_from_content(content: str) -> str:
    """
    Extract article title from note content by finding URLs that start with http and end with #
    
    Args:
        content: Note content to search for URLs
        
    Returns:
        str: Article title or None if no URL found or extraction fails
    """
    # Use regex to find URLs that start with http and end with # (not including the #)
    import re
    url_pattern = r'(https?://[^#\s]+)(?=#)'
    match = re.search(url_pattern, content)
    
    if not match:
        return None
    
    # Extract title from the found URL
    page_url = match.group(1)
    return extract_article_title_from_url(page_url)


def fetch_article_content(url: str) -> dict:
    """
    Fetch article content using newspaper3k and readability-lxml
    
    Args:
        url: URL to fetch content from
        
    Returns:
        dict: Dictionary containing article title, text, and metadata
    """
    try:
        article = Article(url)
        article.download()
        article.parse()
        
        # Use readability-lxml to extract main content
        from readability import Document
        doc = Document(article.html)
        main_content_html = doc.summary()
        
        return {
            'title': article.title or 'Untitled',
            'html': main_content_html or '',
            'authors': article.authors or [],
            'publish_date': article.publish_date,
            'url': url
        }
    except Exception as e:
        console.print(f"[yellow]Warning: Could not fetch content from {url}: {str(e)}[/yellow]")
        return None


def get_notes_by_title_and_date(etapi: ETAPI, title: str, date_str: str) -> list:
    """
    Find all notes with the exact title from the specified date
    
    Args:
        etapi: ETAPI client instance
        title: Note title to search for
        date_str: Date string in format YYYY-MM-DD
        
    Returns:
        list: List of notes with matching title from the specified date
    """
    try:
        # Search for notes with exact title from the past 2 days to capture same-day notes
        search_query = f'note.title = "{title}" note.dateCreated >= TODAY-2'
        results = etapi.search_note(search=search_query)
        
        # Filter to only include notes from the same calendar day
        filtered_results = []
        for note in results.get('results', []):
            note_date = note.get('dateCreated', '')[:10]  # Get just the date part
            if note_date == date_str:
                filtered_results.append(note)
        
        return filtered_results
    except Exception as e:
        console.print(f"[red]Error searching for notes by title and date: {e}[/red]")
        return []


def merge_lien_inclus_notes(etapi: ETAPI, notes: list, verbose: bool = True) -> dict:
    """
    Process notes with #link label that start with "Lien inclus" by merging duplicates
    and updating note titles with article titles extracted using newspaper3k.
    Always looks for pageUrl and updates title, even if no duplicates exist.
    
    Args:
        etapi: ETAPI client instance
        notes: List of notes to process
        verbose: Whether to show progress information
        
    Returns:
        dict: Processing results with success/failure counts
    """
    results = {
        'total': len(notes),
        'processed': 0,
        'merged': 0,
        'titles_updated': 0,
        'errors': []
    }
    
    if verbose:
        console.print(f"[blue]Processing 'Lien inclus' notes for merging and title updates...[/blue]")
    
    for note in track(notes, description="Processing 'Lien inclus' notes..."):
        try:
            note_id = note['noteId']
            title = note['title'].strip()
            
            # Skip if not a "Lien inclus" note
            if not title.startswith("Lien inclus"):
                continue
            
            # Get the date of this note (format as YYYY-MM-DD for searching)
            note_details = etapi.get_note(note_id)
            date_created = note_details.get('dateCreated', '')[:10]  # Get just the date part
            
            # Find all notes with the same title from the same day
            duplicate_notes = get_notes_by_title_and_date(etapi, title, date_created)
            
            # Determine which note to process (oldest if duplicates exist, current if not)
            if len(duplicate_notes) <= 1:
                # No duplicates found - process the current note
                target_note = note
                target_note_id = note_id
                if verbose:
                    console.print(f"[dim]No duplicates found for: {title} - processing current note[/dim]")
            else:
                # Duplicates found - merge them into the oldest note
                # Sort by creation date to get the oldest first
                duplicate_notes.sort(key=lambda x: x.get('dateCreated', ''))
                
                # Get the oldest note (first in sorted list)
                target_note = duplicate_notes[0]
                target_note_id = target_note['noteId']
                
                if verbose:
                    console.print(f"[blue]Found {len(duplicate_notes)} duplicates for: {title}[/blue]")
                
                # Merge content from all duplicates into the oldest note
                merged_content = []
                links_found = []
                
                # Get content from the oldest note first
                oldest_content = etapi.get_note_content(target_note_id)
                merged_content.append(oldest_content)
                
                # Process each duplicate note
                for dup_note in duplicate_notes[1:]:  # Skip the oldest one
                    dup_note_id = dup_note['noteId']
                    dup_content = etapi.get_note_content(dup_note_id)
                    
                    # Extract links from the content (look for URLs at the end)
                    lines = dup_content.strip().split('\n')
                    for line in reversed(lines):
                        line = line.strip()
                        if line.startswith('http://') or line.startswith('https://'):
                            links_found.append(line)
                            break  # Only take the last link
                    
                    # Add the content to merged content
                    if dup_content.strip():
                        merged_content.append(dup_content.strip())
                    
                    # Delete the duplicate note
                    try:
                        etapi.delete_note(dup_note_id)
                        if verbose:
                            console.print(f"[green]✓[/green] Deleted duplicate: {dup_note['title']} ({dup_note_id})")
                    except Exception as delete_error:
                        error_msg = f"Failed to delete duplicate note {dup_note_id}: {str(delete_error)}"
                        results['errors'].append(error_msg)
                        if verbose:
                            console.print(f"[red]✗[/red] {error_msg}")
                
                # Update the oldest note with merged content
                final_content = '\n\n'.join(merged_content)
                etapi.update_note_content(target_note_id, final_content)
                
                results['merged'] += 1
                if verbose:
                    console.print(f"[green]✓[/green] Merged {len(duplicate_notes)} notes into: {target_note['title']}")
            
            # Always look for pageUrl and update title, regardless of duplicates
            
            # Get the current content of the target note
            current_content = etapi.get_note_content(target_note_id)
            
            # Find the first HTTP link ending with # in the content
            page_url = None
            
            # Use regex to find first string starting with http and ending with #
            import re
            # Pattern matches: http(s)://anything# (but excludes the # from the result)
            url_pattern = r'(https?://[^#\s]+)(?=#)'
            match = re.search(url_pattern, current_content)
            
            if match:
                page_url = match.group(1)  # Get the URL without the trailing #
            else:
                # Fallback: look for any HTTP link in the content
                lines = current_content.strip().split('\n')
                for line in reversed(lines):
                    line = line.strip()
                    if line.startswith('http://') or line.startswith('https://'):
                        page_url = line
                        break
            
            # Add the link as a #pageUrl label if found
            if page_url:
                etapi.create_attribute(
                    noteId=target_note_id,
                    type='label',
                    name='pageUrl',
                    value=page_url,
                    isInheritable=False
                )
                if verbose:
                    console.print(f"[green]✓[/green] Added pageUrl label: {page_url}")
                
                # Extract article title using newspaper3k and update note title
                article_title = extract_article_title_from_url(page_url)
                if article_title:
                    etapi.patch_note(target_note_id, title=article_title)
                    results['titles_updated'] += 1
                    if verbose:
                        console.print(f"[green]✓[/green] Updated note title to: {article_title}")
            
            results['processed'] += 1
                
        except Exception as e:
            error_msg = f"Error processing 'Lien inclus' note {note['title']}: {str(e)}"
            results['errors'].append(error_msg)
            if verbose:
                console.print(f"[red]✗[/red] {error_msg}")
    
    return results


def process_link_notes(etapi: ETAPI, notes: list, verbose: bool = True) -> dict:
    """
    Process notes with #link label by extracting URLs and fetching content
    
    Args:
        etapi: ETAPI client instance
        notes: List of notes to process
        verbose: Whether to show progress information
        
    Returns:
        dict: Processing results with success/failure counts
    """
    results = {
        'total': len(notes),
        'processed': 0,
        'urls_found': 0,
        'content_fetched': 0,
        'errors': []
    }
    
    if verbose:
        console.print(f"[blue]Processing link notes for URL content...[/blue]")
    
    # Separate "Lien inclus" notes from regular link notes
    lien_inclus_notes = []
    regular_link_notes = []
    
    for note in notes:
        if note['title'].strip().startswith("Lien inclus"):
            lien_inclus_notes.append(note)
        else:
            regular_link_notes.append(note)
    
    # Process "Lien inclus" notes with merging logic
    if lien_inclus_notes:
        lien_results = merge_lien_inclus_notes(etapi, lien_inclus_notes, verbose)
        results['processed'] += lien_results['processed']
        results['merged'] = lien_results['merged']
        results['errors'].extend(lien_results['errors'])
    
    # Process regular link notes with URL fetching (existing logic)
    for note in track(regular_link_notes, description="Processing regular link notes..."):
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
            
            # Get note content
            content = etapi.get_note_content(note_id)
            
            # Extract URLs from content
            urls = extract_urls_from_text(content)
            
            if not urls:
                if verbose:
                    console.print(f"[dim]No URLs found in: {note['title']}[/dim]")
                continue
            
            results['urls_found'] += len(urls)
            
            # Process each URL found
            for url in urls:
                try:
                    # Fetch article content
                    article_data = fetch_article_content(url)
                    
                    if not article_data:
                        continue
                    
                    # Create attributes for metadata instead of adding to content
                    
                    # Add URL attribute
                    etapi.create_attribute(
                        noteId=note_id,
                        type='label',
                        name='pageUrl',
                        value=url,
                        isInheritable=False
                    )
                    
                    # Add authors attribute if available
                    if article_data['authors']:
                        etapi.create_attribute(
                            noteId=note_id,
                            type='label',
                            name='authors',
                            value=', '.join(article_data['authors']),
                            isInheritable=False
                        )
                    
                    # Add publish date attribute if available
                    if article_data['publish_date']:
                        publish_date_str = article_data['publish_date'].strftime('%Y-%m-%d') if hasattr(article_data['publish_date'], 'strftime') else str(article_data['publish_date'])
                        etapi.create_attribute(
                            noteId=note_id,
                            type='label',
                            name='date',
                            value=publish_date_str,
                            isInheritable=False
                        )
                    
                    # Add template relation attribute
                    # etapi.create_attribute(
                    #     noteId=note_id,
                    #     type='relation',
                    #     name='template',
                    #     value='OYj9NF0MjC4X',
                    #     isInheritable=False
                    # )
                    
    
                    # Update the note content
                    etapi.update_note_content(note_id, content=article_data['html'])
                    results['content_fetched'] += 1
                    
                    if verbose:
                        console.print(f"[green]✓[/green] Updated note '{note['title']}' with content from {url}")
                    
                except Exception as url_error:
                    error_msg = f"Error processing URL {url} in note {note['title']}: {str(url_error)}"
                    results['errors'].append(error_msg)
                    if verbose:
                        console.print(f"[red]✗[/red] {error_msg}")
            
            results['processed'] += 1
            
        except Exception as e:
            error_msg = f"Error processing link note {note['title']}: {str(e)}"
            results['errors'].append(error_msg)
            if verbose:
                console.print(f"[red]✗[/red] {error_msg}")
    
    return results



def process_read_notes(etapi: ETAPI, notes: list, verbose: bool = True) -> dict:
    """
    Process notes with #clipType label by reading note content, 
    extracting HTML tags with background color OR links, 
    removing background colors from highlights,
    recreating note content with only extracted highlighted text and links,
    and merging into paragraphs while preserving original paragraph structure
    
    Args:
        etapi: ETAPI client instance
        notes: List of notes to process
        verbose: Whether to show progress information
        
    Returns:
        dict: Processing results with success/failure counts
    """
    results = {
        'total': len(notes),
        'processed': 0,
        'highlights_extracted': 0,
        'errors': []
    }
    
    if verbose:
        console.print(f"[blue]Processing read notes for highlighted content and links...[/blue]")
    
    for note in track(notes, description="Processing read notes..."):
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
            
            # Get note content
            content = etapi.get_note_content(note_id)
            
            if not content.strip():
                if verbose:
                    console.print(f"[dim]No content found in: {note['title']}[/dim]")
                continue
            
            # Parse HTML content
            soup = BeautifulSoup(content, 'html.parser')
            
            extracted_elements_with_context = []
            
            # Function to check if element has background color
            def has_background_color(element):
                if not hasattr(element, 'get'):
                    return False
                style = element.get('style', '').lower()
                return 'background-color' in style
            
            # Function to remove background color from an element
            def remove_background_color(element):
                """Remove background-color from style attribute"""
                if hasattr(element, 'get') and element.get('style'):
                    style = element['style']
                    # Remove background-color property
                    import re
                    style = re.sub(r'background-color\s*:\s*[^;]+;?', '', style)
                    style = re.sub(r';\s*$', '', style)  # Clean up trailing semicolon
                    if style.strip():
                        element['style'] = style
                    else:
                        del element['style']
                
                # Process children recursively - only if element has contents and is a tag
                if hasattr(element, 'contents') and hasattr(element, 'name'):
                    for child in element.contents:
                        if hasattr(child, 'name') and child.name:  # It's a tag element, not text
                            try:
                                remove_background_color(child)
                            except AttributeError:
                                # Skip if child doesn't support these operations
                                continue
            
            # Function to get paragraph context
            def get_paragraph_context(element):
                """Get the paragraph element that contains this element"""
                parent = element.parent
                while parent and parent.name not in ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    parent = parent.parent
                return parent
            
            # Use a set to track processed elements to avoid duplicates
            processed_element_ids = set()
            
            # First, collect all elements that should be extracted in document order
            for element in soup.find_all():
                element_id = id(element)
                
                # Skip if already processed
                if element_id in processed_element_ids:
                    continue
                
                # Check if element has background color OR is a link
                if has_background_color(element) or (element.name == 'a' and element.get('href')):
                    # Mark this element and all its descendants as processed
                    processed_element_ids.add(element_id)
                    for descendant in element.find_all():
                        processed_element_ids.add(id(descendant))
                    
                    # Get paragraph context
                    paragraph_context = get_paragraph_context(element)
                    
                    # Create a copy for processing
                    element_copy = element.__copy__()
                    
                    # Remove background color from ALL extracted elements (both highlights and links)
                    # This handles cases where links might also have background colors
                    remove_background_color(element_copy)
                    
                    extracted_elements_with_context.append({
                        'element': element_copy,
                        'paragraph': paragraph_context,
                        'original_element': element
                    })
            
            # Process extracted elements with context
            if extracted_elements_with_context:
                paragraphs = []
                current_paragraph_elements = []
                current_paragraph_tag = None
                
                # Group elements by their original paragraph context
                for item in extracted_elements_with_context:
                    element = item['element']
                    paragraph_context = item['paragraph']
                    
                    # If this is a new paragraph context, finish the current one
                    if paragraph_context != current_paragraph_tag:
                        if current_paragraph_elements:
                            # Finish previous paragraph
                            if current_paragraph_elements:
                                paragraph_content = ' '.join(str(elem) for elem in current_paragraph_elements)
                                if paragraph_content.strip():
                                    # Try to reconstruct the original paragraph structure
                                    if current_paragraph_tag and current_paragraph_tag.name in ['p', 'div']:
                                        paragraphs.append(f'<{current_paragraph_tag.name}>{paragraph_content.strip()}</{current_paragraph_tag.name}>')
                                    else:
                                        paragraphs.append(f'<p>{paragraph_content.strip()}</p>')
                        current_paragraph_elements = []
                        current_paragraph_tag = paragraph_context
                    
                    # Add element to current paragraph
                    current_paragraph_elements.append(element)
                
                # Don't forget the last paragraph
                if current_paragraph_elements:
                    paragraph_content = ' '.join(str(elem) for elem in current_paragraph_elements)
                    if paragraph_content.strip():
                        if current_paragraph_tag and current_paragraph_tag.name in ['p', 'div']:
                            paragraphs.append(f'<{current_paragraph_tag.name}>{paragraph_content.strip()}</{current_paragraph_tag.name}>')
                        else:
                            paragraphs.append(f'<p>{paragraph_content.strip()}</p>')
                
                # Create final content
                if paragraphs:
                    final_content = '\n'.join(paragraphs)
                    
                    # Update note content with extracted elements
                    etapi.update_note_content(note_id, content=final_content)
                    results['highlights_extracted'] += 1
                    
                    if verbose:
                        console.print(f"[green]✓[/green] Extracted {len(extracted_elements_with_context)} elements from: {note['title']}")
                else:
                    if verbose:
                        console.print(f"[yellow]⚠[/yellow] No valid content found in extracted elements for: {note['title']}")
            else:
                if verbose:
                    console.print(f"[yellow]⚠[/yellow] No highlighted text or links found in: {note['title']}")
            
            results['processed'] += 1
            
        except Exception as e:
            error_msg = f"Error processing read note {note['title']}: {str(e)}"
            results['errors'].append(error_msg)
            if verbose:
                console.print(f"[red]✗[/red] {error_msg}")
    
    return results


def display_processing_summary(revision_results: dict, link_results: dict, link_processing_results: dict = None, read_processing_results: dict = None):
    """
    Display a summary of the processing results
    
    Args:
        revision_results: Results from revision processing
        link_results: Results from internal link processing
        link_processing_results: Results from link note processing (optional)
        read_processing_results: Results from read note processing (optional)
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
    
    # Link processing summary (if available)
    if link_processing_results:
        table3 = Table(title="Link Note Processing Results")
        table3.add_column("Metric", style="cyan")
        table3.add_column("Value", style="green")
        
        table3.add_row("Total Notes", str(link_processing_results['total']))
        table3.add_row("Processed", str(link_processing_results['processed']))
        if 'merged' in link_processing_results:
            table3.add_row("Merged Groups", str(link_processing_results['merged']))
        if 'titles_updated' in link_processing_results:
            table3.add_row("Titles Updated", str(link_processing_results['titles_updated']))
        if 'urls_found' in link_processing_results:
            table3.add_row("URLs Found", str(link_processing_results['urls_found']))
        if 'content_fetched' in link_processing_results:
            table3.add_row("Content Fetched", str(link_processing_results['content_fetched']))
        table3.add_row("Errors", str(len(link_processing_results['errors'])))
        
        console.print(table3)
    
    if read_processing_results:
        table4 = Table(title="Read Note Processing Results")
        table4.add_column("Metric", style="cyan")
        table4.add_column("Value", style="green")
        
        table4.add_row("Total Notes", str(read_processing_results['total']))
        table4.add_row("Processed", str(read_processing_results['processed']))
        if 'highlights_extracted' in read_processing_results:
            table4.add_row("Highlights Extracted", str(read_processing_results['highlights_extracted']))
        table4.add_row("Errors", str(len(read_processing_results['errors'])))
        
        console.print(table4)
    
    # Combine all errors
    all_errors = []
    all_errors.extend(revision_results['errors'])
    all_errors.extend(link_results['errors'])
    if link_processing_results:
        all_errors.extend(link_processing_results['errors'])
    if read_processing_results:
        all_errors.extend(read_processing_results['errors'])
    
    if all_errors:
        console.print("\n[red]Errors encountered:[/red]")
        for error in all_errors:
            console.print(f"  • {error}")


@click.command(help="Process daily notes: retrieve recent notes, save revisions, add internal links, and fetch URL content for #link labeled notes")
@click.option("--note-id", help="Process only this specific note ID (overrides --days-back)")
@click.option("--days-back", "-d", default=1, help="Number of days to look back (default: 1)")
@click.option("--max-notes", "-m", default=100, type=int, help="Maximum number of notes to process (default: 100)")
@click.option("--env-file", "-e", help="Path to .env file with token", 
              type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option("--global", "is_global", is_flag=True, help="Use global ~/.trilium-py/.env file")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Suppress progress output")
def main(note_id: str, days_back: int, max_notes: int, env_file: str, is_global: bool, verbose: bool, quiet: bool):
    """Process daily notes: retrieve recent notes, save revisions, add internal links, and fetch URL content for notes with #link labels."""
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
        

        # Retrieve notes - either specific note or notes from past days
        if note_id:
            # Process specific note
            if not quiet:
                console.print(f"\n[blue]Retrieving specific note ID: {note_id}...[/blue]")
            
            try:
                specific_note = etapi.get_note(note_id)
                recent_modified_notes = [{
                    'noteId': specific_note['noteId'],
                    'title': specific_note['title'],
                    'type': specific_note['type'],
                    'isProtected': specific_note.get('isProtected', False),
                    'dateModified': specific_note.get('dateModified', '')
                }]
                recent_created_notes = []  # No modified notes when processing specific note
                if not quiet:
                    console.print(f"[green]Found note: {specific_note['title']}[/green]")
            except Exception as e:
                console.print(Panel.fit(
                    f"[bold red]✗ Could not find note ID {note_id}: {str(e)}[/bold red]",
                    title="Note Not Found",
                    border_style="red"
                ))
                sys.exit(1)
        else:
            # Retrieve notes created in the past day(s), keeping original logic for recent_created_notes
            if not quiet:
                console.print(f"\n[blue]Retrieving notes created in the past {days_back} day(s)...[/blue]")
            
            recent_created_notes = get_notes_created_in_past_day(etapi, days_back)
            
            if not quiet:
                console.print(f"[blue]Retrieving notes modified in the past {days_back} day(s)...[/blue]")
            
            recent_modified_notes = get_notes_modified_in_past_days(etapi, days_back)
                    
            if not recent_created_notes:
                console.print("[yellow]No notes found in the specified time period.[/yellow]")
                return
        
        # Calculate and display the date range used for selection
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_back)
        cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')
        current_date_str = datetime.datetime.now().strftime('%Y-%m-%d')
        
        if not quiet:
            console.print(f"[dim]Date range: {cutoff_date_str} to {current_date_str}[/dim]")
            console.print(f"[green]Found {len(recent_created_notes)} notes created in the past {days_back} day(s)[/green]")
        

        # Apply max notes limit if specified to both created and modified notes
        if max_notes is not None and len(recent_created_notes) > max_notes:
            recent_created_notes = recent_created_notes[:max_notes]
            if not quiet:
                console.print(f"[yellow]Limited to processing {max_notes} notes (out of {len(recent_created_notes)} total)[/yellow]")
        
        # Also apply max notes limit to modified notes
        if max_notes is not None and len(recent_modified_notes) > max_notes:
            recent_modified_notes = recent_modified_notes[:max_notes]
            if not quiet:
                console.print(f"[yellow]Limited to processing {max_notes} modified notes (out of {len(recent_modified_notes)} total)[/yellow]")
        

        # Filter notes with #link label from created notes
        link_notes = []
        other_notes = []
        
        for note in recent_created_notes:
            # Check if note has #link label by searching for it
            search_result = etapi.search_note(search=f"note.noteId = '{note['noteId']}' #link")
            if search_result.get('results'):
                link_notes.append(note)
            else:
                other_notes.append(note)
        
        if not quiet and link_notes:
            console.print(f"[blue]Found {len(link_notes)} notes with #link label[/blue]")
        
        # Filter notes with #clipType label from modified notes
        read_notes = []
        
        for note in recent_modified_notes:
            # Check if note has #clipType label by searching for it
            search_result = etapi.search_note(search=f"note.noteId = '{note['noteId']}' #clipType")
            if search_result.get('results'):
                read_notes.append(note)
        
        if not quiet and read_notes:
            console.print(f"[blue]Found {len(read_notes)} notes with #clipType label from modified notes[/blue]")
        

        # Process revisions for other_notes and read_notes
        # This ensures we save revisions before modifying content
        all_revision_notes = other_notes + read_notes
        if all_revision_notes:
            revision_results = process_note_revisions(etapi, all_revision_notes, verbose and not quiet)
        else:
            revision_results = {'total': 0, 'successful': 0, 'failed': 0, 'errors': []}
        

        # Add internal links only for notes without #link label
        link_results = add_internal_links_to_notes(etapi, other_notes, verbose and not quiet)
        
        # Process link notes (URL fetching and content addition) - no revisions saved for these
        link_processing_results = None
        if link_notes:
            link_processing_results = process_link_notes(etapi, link_notes, verbose and not quiet)
        
        # Process read notes - no revisions saved for these either
        read_processing_results = None
        if read_notes:
            read_processing_results = process_read_notes(etapi, read_notes, verbose and not quiet)
        
        # Display summary
        if not quiet:
            display_processing_summary(revision_results, link_results, link_processing_results, read_processing_results)
        
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
