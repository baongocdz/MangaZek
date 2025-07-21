import subprocess
import sys

def install_package(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def main():
    packages = ["requests", "flask", "beautifulsoup4"]
    for package in packages:
        try:
            print(f"Installing {package}...")
            install_package(package)
            print(f"{package} installed successfully.")
        except Exception as e:
            print(f"Error installing {package}: {e}")

if __name__ == "__main__":
    main()