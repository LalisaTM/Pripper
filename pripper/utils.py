# pripper/utils.py
from colorama import init, Fore

# Initialize colorama once
init(autoreset=True)

def print_info(msg):    print(Fore.CYAN   + '[*] ' + str(msg))
def print_success(msg): print(Fore.GREEN  + '[+] ' + str(msg))
def print_error(msg):   print(Fore.RED    + '[-] ' + str(msg))
def print_warning(msg): print(Fore.YELLOW + '[!] ' + str(msg))
