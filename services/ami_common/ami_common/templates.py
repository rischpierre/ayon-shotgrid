import os
from jinja2 import ChoiceLoader, FileSystemLoader, Environment


def create_template_loader(*search_dirs):
    """Create a Jinja2 template loader that searches multiple directories.

    Args:
        *search_dirs: Variable number of directory paths to search for templates

    Returns:
        jinja2.ChoiceLoader that searches directories in order
    """
    loaders = [FileSystemLoader(d) for d in search_dirs if os.path.exists(d)]
    return ChoiceLoader(loaders) if loaders else FileSystemLoader(".")


def create_jinja_environment(*search_dirs):
    """Create a configured Jinja2 environment with custom loader.

    Args:
        *search_dirs: Variable number of directory paths to search for templates

    Returns:
        jinja2.Environment configured with ChoiceLoader
    """
    loader = create_template_loader(*search_dirs)
    return Environment(loader=loader)
