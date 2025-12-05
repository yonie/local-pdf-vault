# Contributing to LocalPDFVault

Thank you for considering contributing to LocalPDFVault! Your help makes this privacy-focused tool better for everyone.

## Code of Conduct

This project is built on respect and professionalism. By participating, you agree to maintain a welcoming and inclusive environment for all contributors.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates. When creating a bug report, include:

- **Clear, descriptive title**
- **Exact steps to reproduce** the problem
- **Expected vs. actual behavior**
- **Screenshots** (if applicable)
- **Environment details**:
  - OS (Windows, macOS, Linux + version)
  - Python version (`python --version`)
  - Ollama version (`ollama --version`)
  - Model name used

**Example Bug Report Template:**
```markdown
## Bug: PDF Preview Not Loading

**Environment:**
- OS: Windows 11
- Python: 3.10.5
- Ollama: 0.1.14
- Model: qwen3-vl:30b-a3b-instruct-q4_K_M

**Steps to Reproduce:**
1. Index a folder with PDFs
2. Click on any document in search results
3. Preview panel stays loading

**Expected:** PDF preview should display
**Actual:** Infinite loading spinner

**Console Errors:** [paste any browser console errors]
```

### Suggesting Enhancements

Enhancement suggestions are welcome! When creating one:

- **Use a clear, descriptive title**
- **Provide detailed description** of the enhancement
- **Explain the problem** it solves or value it adds
- **Describe alternatives** you've considered
- **Show examples** or mockups if applicable

### Pull Requests

We love pull requests! Here's how to contribute code:

1. **Fork the repository**
2. **Create your feature branch** (`git checkout -b feature/amazing-feature`)
3. **Make your changes**
4. **Test thoroughly**
5. **Commit with clear messages** (`git commit -m 'Add amazing feature'`)
6. **Push to your branch** (`git push origin feature/amazing-feature`)
7. **Open a Pull Request**

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/localpdfvault.git
cd localpdfvault

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install development tools
pip install pytest black flake8 mypy
```

## Code Style Guidelines

### Python Code

- **Follow PEP 8** style guide
- **Use meaningful names** for variables, functions, and classes
- **Add docstrings** to all functions and classes
- **Keep functions focused** - one responsibility per function
- **Add comments** for complex logic only (code should be self-documenting)

**Example:**
```python
def extract_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata from a PDF file using vision model.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Dictionary containing extracted metadata
        
    Raises:
        FileNotFoundError: If PDF file doesn't exist
        ValueError: If file is not a valid PDF
    """
    # Implementation here
```

### Code Formatting

Before committing, format your code:

```bash
# Format code
black pdfscanner.py webapp.py

# Check linting
flake8 pdfscanner.py webapp.py

# Type checking (optional but recommended)
mypy pdfscanner.py webapp.py
```

### JavaScript/HTML/CSS

- **Use 4-space indentation**
- **Use meaningful variable names**
- **Add comments for complex UI logic**
- **Keep functions small and focused**
- **Follow existing code style**

## Testing

```bash
# Run tests (when test suite exists)
pytest

# Run specific test file
pytest tests/test_scanner.py

# Run with coverage
pytest --cov=pdfscanner
```

### Manual Testing Checklist

Before submitting a PR, test these scenarios:

- [ ] Index new folder with PDFs
- [ ] Search functionality works
- [ ] PDF preview displays correctly
- [ ] Re-indexing existing files
- [ ] Error handling for corrupted PDFs
- [ ] Ollama connection errors handled gracefully
- [ ] Database operations succeed
- [ ] Web UI responsive on mobile
- [ ] All buttons/links functional

## Project Structure

```
localpdfvault/
├── pdfscanner.py          # Core: PDF scanning and AI analysis
│   ├── DatabaseManager    # SQLite operations
│   └── PDFScanner         # Main scanning logic
│
├── webapp.py              # Web server and API
│   ├── Flask routes       # HTTP endpoints
│   └── Background tasks   # Indexing operations
│
├── static/
│   ├── app.js            # Frontend JavaScript
│   │   ├── Search logic
│   │   ├── PDF viewer
│   │   └── UI interactions
│   └── style.css         # UI styling
│
├── templates/
│   └── index.html        # Main web interface
│
├── requirements.txt       # Python dependencies
├── README.md             # User documentation
├── CONTRIBUTING.md       # This file
├── LICENSE               # MIT License
└── AGENTS.md            # AI development docs
```

## Key Areas for Contribution

### 🔍 1. Vision Model Support

**Easy:**
- Test with different Ollama models
- Document model performance comparisons
- Add model-specific prompt tuning

**Medium:**
- Implement model auto-selection based on file type
- Add fallback model chains

**Advanced:**
- Support non-Ollama vision models
- Implement ensemble model voting

### ⚡ 2. Performance

**Easy:**
- Profile and identify bottlenecks
- Add loading indicators where missing
- Optimize database queries

**Medium:**
- Implement parallel PDF processing
- Add caching for frequent searches
- Optimize memory usage

**Advanced:**
- Implement incremental indexing
- Add distributed processing support
- Database query optimization

### 🎨 3. Web Interface

**Easy:**
- Improve mobile responsiveness
- Add dark/light mode toggle
- Enhance accessibility (ARIA labels, etc.)

**Medium:**
- Add advanced search filters
- Implement drag-and-drop file upload
- Add batch operations UI

**Advanced:**
- Real-time collaborative search
- Advanced PDF annotations
- Custom metadata fields

### 📚 4. Documentation

**Easy:**
- Fix typos and improve clarity
- Add more usage examples
- Create video tutorials

**Medium:**
- Write integration guides
- Add architecture diagrams
- Translate documentation

**Advanced:**
- Create API documentation
- Write development guides
- Build interactive tutorials

### 🧪 5. Testing

**Easy:**
- Add unit tests for utility functions
- Test with various PDF types
- Document test cases

**Medium:**
- Add integration tests
- Implement CI/CD
- Add performance benchmarks

**Advanced:**
- Fuzzing for edge cases
- Stress testing
- Security testing

## Commit Message Guidelines

Use clear, descriptive commit messages:

```bash
# Good
git commit -m "Add fuzzy search for document titles"
git commit -m "Fix PDF preview zoom on mobile devices"
git commit -m "Improve database query performance by 40%"

# Bad
git commit -m "Fixed stuff"
git commit -m "Updates"
git commit -m "WIP"
```

**Commit Message Format:**
```
<type>: <brief description>

[Optional detailed explanation]

[Optional footer with issue references]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

**Example:**
```
feat: Add batch PDF re-indexing support

Implements ability to re-index multiple PDFs at once
through the web interface. Includes progress tracking
and error handling for failed re-indexes.

Closes #42
```

## Pull Request Process

1. **Update documentation** if adding features
2. **Add tests** for new functionality
3. **Ensure all tests pass**
4. **Update CHANGELOG.md** if applicable
5. **Request review** from maintainers

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tested locally
- [ ] Added unit tests
- [ ] Added integration tests

## Screenshots (if applicable)
[Add screenshots here]

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-reviewed code
- [ ] Commented complex sections
- [ ] Updated documentation
- [ ] No new warnings
- [ ] Added tests
- [ ] All tests pass
```

## Questions or Need Help?

- 💬 **Discussions**: Use [GitHub Discussions](https://github.com/yonie/localpdfvault/discussions)
- 🐛 **Issues**: Check [existing issues](https://github.com/yonie/localpdfvault/issues)
- 📧 **Contact**: Open an issue or discussion

## Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Given credit in documentation

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Thank you for helping make LocalPDFVault better! 🎉**