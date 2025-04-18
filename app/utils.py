import pandas as pd
from datetime import datetime

def save_to_excel(data, filename_prefix="reddit_results"):
    filename = f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df = pd.DataFrame(data)
    df.to_excel(filename, index=False)
    return filename