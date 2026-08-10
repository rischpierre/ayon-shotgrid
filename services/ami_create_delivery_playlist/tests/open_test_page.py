import webbrowser
from pathlib import Path

def open_test_page():
    test_page = Path(__file__).parent /  "test_request.html"
    webbrowser.open(test_page.as_uri())

if __name__ == '__main__':
    open_test_page()