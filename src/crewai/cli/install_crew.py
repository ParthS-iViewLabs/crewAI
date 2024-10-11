import subprocess

import click


def install_crew() -> None:
    """
    Install the crew by running the UV command to lock and install.
    """
    try:
        subprocess.run(["uv", "sync"], check=True, capture_output=False, text=True)

    except subprocess.CalledProcessError as e:
        click.echo(f"An error occurred while running the crew: {e}", err=True)
        click.echo(e.output, err=True)

    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
