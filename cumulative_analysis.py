import pandas as pd
import os

def aggregate_incremental_updates():
    all_updates = []
    base_dir = "output"
    for handle in os.listdir(base_dir):
        file_path = os.path.join(base_dir, handle, "incremental_updates.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path, names=['timestamp', 'account'])
            df['followed by'] = handle  # Add the handle to each row
            all_updates.append(df)

    combined_df = pd.concat(all_updates, ignore_index=True)
    deduped_df = combined_df.drop_duplicates(subset=['account', 'followed by'])
    return deduped_df

incremental_updates_df = aggregate_incremental_updates()
incremental_updates_df.to_csv('incremental_updates_list.csv', index=False)
print("Incremental updates list saved to 'incremental_updates_list.csv'.")
