import pickle

def load_and_print_cookies_pickle(file_path):
    # Open and load the pickle file
    try:
        with open(file_path, 'rb') as file:  # Note the 'rb' mode for reading binary
            cookies = pickle.load(file)

        # Print details of each cookie
        for cookie in cookies:
            print("Cookie:")
            for key, value in cookie.items():
                print(f"  {key}: {value}")
    except FileNotFoundError:
        print("Pickle file not found.")
    except pickle.UnpicklingError:
        print("Error unpickling the file.")
    except Exception as e:
        print(f"An error occurred: {e}")

# Replace 'path_to_your_cookies_file.pkl' with the actual path to your cookies file
load_and_print_cookies_pickle('/root/followfeed/cookies.pkl')
