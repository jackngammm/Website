import pandas as pd

hotel_data = pd.read_csv('marriott_hotels_dataset.csv')

print(hotel_data[(hotel_data['Location'] == 'Atlanta') & (hotel_data['Price_Per_Night'] <= 200)][['Hotel_Name', 'Location', 'Price_Per_Night']])
