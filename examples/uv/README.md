# Using Trilium Py with UV

Examples of Trilium-py scripts that can be run using [**`uv`** from Astral](https://github.com/astral-sh/uv)
without having to install anything other than _uv_ ahead of time, not even python.

1. Install uv,
2. run a script.

```
uv run <scipt-name> <parameters>
```

## Development

Write standalone scripts with dependencies declared using [inline metadata](https://packaging.python.org/en/latest/specifications/inline-script-metadata/#inline-script-metadata) (PEP 723) and execute with `uv run`. For example:

```python
'''demo: hello world from Trilium-py'''
# /// script
# dependencies = [
#   "click",
#   "rich",
#   "trilium-py",
# ]
# ///
import rich
rich.print("hello world from Trilium-py :)")
```

Then execute :

    uv run hello-world.py

Script names follow function names, for example `ea_app_info.py` for `ea.app_info()`.


## Examples

### Get Trilium Token
Implementation of README.md#etapi-initialization

```shell
❯ uv run get_etapi_token.py --help
Usage: get_etapi_token.py [OPTIONS] SERVER_URL PASSWORD

  Get and save Trilium ETAPI token

Options:
  -e, --env-file FILE  Path to .env file to save token
  --global             Save token to global ~/.trilium-py/.env file
  --help               Show this message and exit.

❯ uv run get_etapi_token.py http://localhost:8080 tttt
Connecting to Trilium server at http://localhost:8080...
╭────────────────── Trilium Authentication Successful ──────────────────╮
│ ✓ Successfully obtained token from Trilium 0.92.3-beta                │
│                                                                       │
│ Token saved to: /var/home/me/dev/trilium-py/examples/uv/.env          │
│                                                                       │
│ You can now use Trilium-py tools that require Trilium authentication. │
╰───────────────────────────────────────────────────────────────────────╯
```

### Show Trilium App Info

Implementation of README.md#-basic-etapi-usage

```shell
❯ uv run ea_app_info.py --help
Usage: ea_app_info.py [OPTIONS]

  Display Trilium server information

Options:
  -e, --env-file FILE  Path to .env file with token
  --global             Use global ~/.trilium-py/.env file
  --help               Show this message and exit.

❯ uv run ea_app_info.py 
╭─────────────────────── Connection Information ───────────────────────╮
│ Configuration Source: /var/home/matt/dev/trilium-py/examples/uv/.env │
│ Server URL: http://localhost:8080                                    │
│ Token: ********...mqo=                                               │
╰──────────────────────────────────────────────────────────────────────╯
Connecting to Trilium server...
                     Trilium Server Information                      
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Property               ┃ Value                                    ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ appVersion             │ 0.92.3-beta                              │
│ dbVersion              │ 228                                      │
│ nodeVersion            │ v23.9.0                                  │
│ syncVersion            │ 34                                       │
│ buildDate              │ 2025-03-07T21:59:10Z                     │
│ buildRevision          │ e76601cd21c0fe0d50745affe582f61bcd752fec │
│ dataDirectory          │ /var/home/matt/dev/trilium/data          │
│ clipperProtocolVersion │ 1.0                                      │
│ utcDateTime            │ 2025-03-14T03:01:34.341Z                 │
└────────────────────────┴──────────────────────────────────────────┘
```

### Upload Markdown Folder

Implementation of README.md#bulk-upload-markdown-files-in-a-folder

With extra logic to accommodate sub-folder of assets (e.g. images) with same name as the .md file. Avoids situation where this input:

    source_dir/
        Foobaz.md
        Foobaz/hero-image.jpg
        Foobaz/another-pic.jpg
    
Would create in Trilium:

    destination_note/
        Foobaz
            hero-image.jpg
            another-pic.jpg
        Foobaz
            (empty)

Note: any content in the sub-folder that is not linked from the .md will be left behind.


```shell
❯ uv run ea_upload_md_folder.py --help
Usage: ea_upload_md_folder.py [OPTIONS]

  Bulk upload Markdown files to Trilium

Options:
  -f, --folder DIRECTORY          Path to folder containing Markdown files
                                  [required]
  -p, --parent-note TEXT          Title of the parent note to upload files to
                                  [required]
  -e, --env-file FILE             Path to .env file with token
  --global                        Use global ~/.trilium-py/.env file
  -if, --ignore-folders TEXT      Additional folders to ignore (comma-
                                  separated)
  -ifl, --ignore-folder-list FILE
                                  Path to a text file with folders to ignore
                                  (one per line)
  -ig, --ignore-files TEXT        Files to ignore (comma-separated)
  -ip, --include-pattern TEXT     File patterns to include (comma-separated)
  --help                          Show this message and exit.
```

```shell
❯ uv run ea_upload_md_folder.py -f ./sample/logseq/ -p import-test --ignore-folders assets,.git

Server URL: http://localhost:8080
Token: GgS8B***********************************************Zmqo=
Config source: /var/home/matt/dev/trilium-py/examples/uv/.env
Connecting to Trilium server...
Searching for note with title: import-test
Note with title 'import-test' not found
Would you like to create a new note titled 'import-test'? [y/n] (y): 
Created new parent note with ID: zNhyh5il49r0
╭────────────────────────── Upload Configuration ───────────────────────────╮
│ Folder to upload: /var/home/matt/dev/trilium-py/examples/uv/sample/logseq │
│ Parent note title: import-test                                            │
│ Folders to ignore: assets, .git                                           │
│ Files to ignore:                                                          │
│ Include patterns: .md                                                     │
╰───────────────────────────────────────────────────────────────────────────╯
Proceed with upload? [y/n] (y): 
Starting upload...
2025-03-18 05:31:14.651 | INFO     | trilium_py.client:upload_md_folder:1144 - /var/home/matt/dev/trilium-py/examples/uv/sample/logseq
2025-03-18 05:31:14.652 | INFO     | trilium_py.client:upload_md_folder:1156 - ==============
2025-03-18 05:31:14.652 | INFO     | trilium_py.client:upload_md_folder:1157 - root /var/home/matt/dev/trilium-py/examples/uv/sample/logseq
2025-03-18 05:31:14.652 | INFO     | trilium_py.client:upload_md_folder:1158 - root_folder_name logseq
2025-03-18 05:31:14.652 | INFO     | trilium_py.client:upload_md_folder:1159 - rel_path .
2025-03-18 05:31:14.652 | INFO     | trilium_py.client:upload_md_folder:1163 - files
2025-03-18 05:31:14.652 | INFO     | trilium_py.client:upload_md_folder:1171 - /var/home/matt/dev/trilium-py/examples/uv/sample/logseq/sample-2.md
2025-03-18 05:31:14.652 | INFO     | trilium_py.client:upload_md_file:951 - /var/home/matt/dev/trilium-py/examples/uv/sample/logseq/sample-2.md
2025-03-18 05:31:14.706 | INFO     | trilium_py.client:upload_md_file:1003 - found images:
2025-03-18 05:31:14.706 | INFO     | trilium_client:upload_md_file:1004 - ['src="./assets/2021-02-19-14_05_19-Window.png" alt="img" /']
2025-03-18 05:31:14.757 | INFO     | trilium_py.client:upload_md_file:1061 - api/images/MMVi0YUHnpuo/img
...snip...
2025-03-18 05:31:14.961 | INFO     | trilium_py.client:upload_md_folder:1177 - dirs
✓ Successfully uploaded Markdown files to 'import-test'
```

Processing Summary
Revision Processing Results
┏━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric        ┃ Value ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Total Notes   │ 5     │
│ Successful    │ 5     │
│ Failed        │ 0     │
└───────────────┴───────┘
Internal Link Processing Results
┏━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric        ┃ Value ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Total Notes   │ 5     │
│ Processed     │ 5     │
│ Errors        │ 0     │
└───────────────┴───────┘

✓ Daily notes processing completed successfully!
### Daily Notes Processor

Automatically process notes created in the past day by saving revisions, adding internal links, and fetching URL content for notes with #link labels.

**New Features:**
- **Link Processing**: Notes with `#link` labels are automatically processed to extract URLs and fetch article content
- **URL Content Fetching**: Uses newspaper3k to fetch article content from URLs found in notes
- **Automatic Tagging**: Adds `#url="insert url here"` tags to processed notes
- **Content Integration**: Appends fetched article content to the original note

```shell
❯ uv run daily_notes_processor.py --help
Usage: daily_notes_processor.py [OPTIONS]

  Process daily notes: retrieve recent notes, save revisions, add internal
  links, and fetch URL content for #link labeled notes

Options:
  -d, --days-back INTEGER  Number of days to look back (default: 1)
  -m, --max-notes INTEGER  Maximum number of notes to process (default: 100)
  -e, --env-file FILE      Path to .env file with token
  --global                 Use global ~/.trilium-py/.env file
  -v, --verbose            Enable verbose output
  -q, --quiet              Suppress progress output
  --help                   Show this message and exit.
```

```shell
❯ uv run daily_notes_processor.py -d 1 --verbose
╭─────────────────────── Connection Information ───────────────────────╮
│ Configuration Source: /var/home/matt/dev/trilium-py/examples/uv/.env │
│ Server URL: http://localhost:8080                                    │
│ Token: ********...mqo=                                               │
╰──────────────────────────────────────────────────────────────────────╯
Connecting to Trilium server...
✓ Connected to Trilium 0.92.3-beta

Retrieving notes created in the past 1 day(s)...
Date range: 2025-03-13 to 2025-03-14
Found 5 notes created in the past 1 day(s)
Found 2 notes with #link label
Processing revisions for 5 notes...
✓ Revision saved for: Meeting Notes
✓ Revision saved for: Project Ideas
✓ Revision saved for: Daily Journal
✓ Revision saved for: Research Notes
✓ Revision saved for: Code Snippets
Adding internal links to 5 notes...
✓ Processed internal links for: Meeting Notes
✓ Processed internal links for: Project Ideas
✓ Processed internal links for: Daily Journal
✓ Processed internal links for: Research Notes
✓ Processed internal links for: Code Snippets
Processing link notes for URL content...
✓ Updated note 'Interesting Article' with content from https://example.com/article
✓ Updated note 'Tech News' with content from https://techcrunch.com/story
Processing Summary
Revision Processing Results
┏━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric        ┃ Value ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Total Notes   │ 5     │
│ Successful    │ 5     │
│ Failed        │ 0     │
└───────────────┴───────┘
Internal Link Processing Results
┏━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric        ┃ Value ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Total Notes   │ 5     │
│ Processed     │ 5     │
│ Errors        │ 0     │
└───────────────┴───────┘
Link Note Processing Results
┏━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric        ┃ Value ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Total Notes   │ 2     │
│ Processed     │ 2     │
│ URLs Found    │ 3     │
│ Content Fetched│ 2     │
│ Errors        │ 0     │
└───────────────┴───────┘

✓ Daily notes processing completed successfully!
```

**How Link Processing Works:**

1. **Detection**: The script identifies notes with the `#link` label
2. **URL Extraction**: Extracts URLs from the note content using regex patterns
3. **Content Fetching**: Uses newspaper3k to fetch article content from each URL
4. **Note Updates**: 
   - Adds `#url="insert url here"` tag to the note
   - Appends the fetched article content below the original content
   - Includes metadata like authors and publication date when available

**Example Note Transformation:**

**Before:**
```
#link

Check out this interesting article: https://example.com/article
```

**After:**
```
#url="https://example.com/article"
#link

Check out this interesting article: https://example.com/article

---
**Content from https://example.com/article:**

[Full article text here]

**Authors:** John Doe, Jane Smith
**Published:** 2025-03-14
```

**New Features:**

- **Max Notes Limit**: Use `-m/--max-notes` to limit the number of notes processed (default: 10). Useful when you have many notes and want to process only a subset.
- **Date Range Display**: The script now shows the date range used for note selection (e.g., "Date range: 2025-03-13 to 2025-03-14").

Example with max notes limit:
```shell
❯ uv run daily_notes_processor.py -d 7 --max-notes 20
Retrieving notes created in the past 7 day(s)...
Date range: 2025-03-07 to 2025-03-14
Found 25 notes created in the past 7 day(s)
Limited to processing 20 notes (out of 25 total)
Processing revisions for 20 notes...
...
```

Example using default limit (10 notes):
```shell
❯ uv run daily_notes_processor.py -d 7
Retrieving notes created in the past 7 day(s)...
Date range: 2025-03-07 to 2025-03-14
Found 25 notes created in the past 7 day(s)
Limited to processing 10 notes (out of 25 total)
Processing revisions for 10 notes...
...
```
==================================================
Processing Summary
==================================================
Revision Processing Results
┏━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric        ┃ Value ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Total Notes   │ 5     │
│ Successful    │ 5     │
│ Failed        │ 0     │
└───────────────┴───────┘
Internal Link Processing Results
┏━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric        ┃ Value ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Total Notes   │ 5     │
│ Processed     │ 5     │
│ Errors        │ 0     │
└───────────────┴───────┘

✓ Daily notes processing completed successfully!
