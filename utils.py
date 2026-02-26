class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    RESET = '\033[0m'
    
    @staticmethod
    def success(text):
        return f"{Colors.GREEN}{text}{Colors.RESET}"
    
    @staticmethod
    def error(text):
        return f"{Colors.RED}{text}{Colors.RESET}"
    
    @staticmethod
    def warning(text):
        return f"{Colors.YELLOW}{text}{Colors.RESET}"
    
    @staticmethod
    def info(text):
        return f"{Colors.CYAN}{text}{Colors.RESET}"
    
    @staticmethod
    def highlight(text):
        return f"{Colors.BOLD}{Colors.WHITE}{text}{Colors.RESET}"
    
    @staticmethod
    def profit(value):
        if value >= 0:
            return f"{Colors.GREEN}+${value:.2f}{Colors.RESET}"
        else:
            return f"{Colors.RED}-${abs(value):.2f}{Colors.RESET}"
    
    @staticmethod
    def percent(value):
        if value >= 0:
            return f"{Colors.GREEN}+{value:.2f}%{Colors.RESET}"
        else:
            return f"{Colors.RED}{value:.2f}%{Colors.RESET}"
