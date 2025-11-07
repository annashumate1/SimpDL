# SimpDL

A Python-based GUI application for downloading images from SimpCity forums using cookie-based authentication.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)

## Features

- **Hybrid Download System**: Combines browser automation (Playwright) for initial page access with fast HTTP requests for bulk downloads
- **Cookie-Based Authentication**: Bypasses captcha issues and login detection
- **GUI Interface**: Built with ttkbootstrap for modern appearance and ease of use
- **Multi-Page Support**: Automatically processes paginated forum threads
- **Progress Tracking**: Real-time download status and progress indicators
- **Automatic Organization**: Downloads are organized by thread name in designated folders

## Requirements

- Python 3.7 or higher
- Chromium-based browser (for Playwright)
- Active account on the target platform

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/annashumate1/SimpDL.git
   cd SimpDL
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright browsers**
   ```bash
   playwright install chromium
   ```

4. **Configure the application**
   ```bash
   cp config/config.example.json config/config.json
   cp config/manual_cookies.example.json config/manual_cookies.json
   cp config/urls.example.txt config/urls.txt
   ```

## Configuration

### Cookie Extraction

Authentication uses browser cookies rather than username/password credentials.

1. Run the cookie extraction utility:
   ```bash
   python extract_cookie_header.py
   ```

2. Follow the prompts:
   - Navigate to `https://simpcity.cr` in your browser
   - Log in to your account
   - Open Developer Tools (F12)
   - Switch to the Network tab
   - Refresh the page
   - Select the first request
   - Locate the `Cookie:` header in Request Headers
   - Copy the entire cookie string
   - Paste into the terminal when prompted

### Download Directory

Set your preferred download location in `config/config.json`:

```json
{
    "output_directory": "/path/to/downloads"
}
```

Alternatively, use the GUI to browse and select a folder.

### URL Management

Add target URLs to `config/urls.txt`, one per line:

```
https://simpcity.cr/threads/example.12345/page-1
https://simpcity.cr/threads/example.12345/page-2
```

Or use the built-in link generator to create paginated URLs automatically.

## Usage

Launch the application:

```bash
python main.py
```

### GUI Navigation

- **Download Settings**: Configure output directory
- **Manage Download URLs**: Add or remove target URLs
- **Generate Links**: Auto-create paginated thread URLs
- **Download Images**: Execute the download process

### Download Process

1. Click "Download Images" in the sidebar
2. Click "Start Hybrid Download"
3. Monitor progress in real-time
4. Downloaded files are saved to configured directory, organized by thread

## Technical Details

### Hybrid Approach

The application uses a two-tier download strategy:

1. **First Page**: Playwright-based browser automation handles additional authentication challenges
2. **Subsequent Pages**: Direct HTTP requests with authenticated cookies for faster processing

This approach optimizes for both reliability and performance.

### Cookie Management

Cookies typically remain valid for 1-4 weeks. When authentication fails, re-run the cookie extraction process.

## Troubleshooting

### HTTP 403 Errors

**Symptom**: Access denied errors during download

**Solution**: Extract fresh cookies using `extract_cookie_header.py`

### Missing Configuration

**Symptom**: Application reports missing cookies or configuration

**Solution**: Verify `config/manual_cookies.json` and `config/config.json` exist and are properly formatted

### Slow Performance

**Possible Causes**:
- Network congestion
- Server-side rate limiting
- High traffic on target server

**Solutions**:
- Verify network connection
- Retry during off-peak hours
- Check for rate limiting messages in logs

### First Page Failures

Page 1 may occasionally fail due to additional anti-automation measures. This is expected behavior. The hybrid system attempts multiple strategies to handle this.

## Project Structure

```
SimpDL/
├── assets/              # Application resources
├── config/              # Configuration files (git-ignored)
├── main.py              # Application entry point
├── config_utils.py      # Configuration management
├── downloader_hybrid.py # Core download logic
├── image_utils.py       # Image validation utilities
├── link_utils.py        # URL generation
├── extract_cookie_header.py  # Cookie extraction tool
└── test_cookies.py      # Cookie validation utility
```

## Security Considerations

Sensitive data is excluded from version control via `.gitignore`:
- `config/config.json`
- `config/manual_cookies.json`
- `config/urls.txt`
- `downloads/`

Never commit authentication credentials or personal data to public repositories.

## Legal Notice

This software is provided for educational purposes only. Users are solely responsible for:

- Compliance with the target platform's Terms of Service
- Adherence to applicable copyright laws
- Following local and international regulations regarding data access and usage

The authors and contributors assume no liability for misuse of this software.

## Contributing

Contributions are welcome. Please:

1. Fork the repository
2. Create a feature branch
3. Implement changes with appropriate documentation
4. Submit a pull request for review

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Support

For issues, bug reports, or feature requests, please use the [GitHub issue tracker](https://github.com/annashumate1/SimpDL/issues).

For direct contact: [Telegram](https://t.me/annashumatelover)

---

**Disclaimer**: This tool is intended for personal archival purposes only. Users must respect intellectual property rights and platform policies.