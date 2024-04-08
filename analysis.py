import pandas as pd
import os


def aggregate_followers():
    all_followers = []
    base_dir = "output"
    for handle in os.listdir(base_dir):
        file_path = os.path.join(base_dir, handle, "cumulative_follows.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path, header=None, names=["follower"])
            all_followers.append(df)

    return pd.concat(all_followers)


all_followers_df = aggregate_followers()


def rank_accounts(df):
    rank_df = df["follower"].value_counts().reset_index()
    rank_df.columns = ["account", "follower_count"]
    rank_df.sort_values(by="follower_count", ascending=False, inplace=True)
    return rank_df


ranked_accounts = rank_accounts(all_followers_df)
print(ranked_accounts)


def consolidate_new_follows():
    new_follows = []
    base_dir = "output"
    for handle in os.listdir(base_dir):
        file_path = os.path.join(base_dir, handle, "incremental_updates.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(
                file_path, header=None, names=["timestamp", "new_follower"]
            )
            df["followed_by"] = handle
            new_follows.append(df)

    return pd.concat(new_follows)


new_follows_df = consolidate_new_follows()


def display_new_follows(df):
    sorted_df = df.sort_values(by="timestamp", ascending=False)
    return sorted_df


sorted_new_follows = display_new_follows(new_follows_df)
print(sorted_new_follows)
