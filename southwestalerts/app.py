import logging
import requests
import sys

from southwest import Southwest
import settings


def check_for_price_drops(username, password, email):
    southwest = Southwest(username, password)
    for trip in southwest.get_upcoming_trips()['trips']:
        for flight in trip['flights']:
            passenger = flight['passengers'][0]
            record_locator = flight['recordLocator']
            cancellation_details = southwest.get_cancellation_details(record_locator, passenger['firstName'], passenger['lastName'])
            itinerary_price = cancellation_details['availableFunds']['nonrefundableAmountCents'] / 100.00
            # Calculate total for all of the legs of the flight
            matching_flights_price = 0
            for origination_destination in cancellation_details['itinerary']['originationDestinations']:
                departure_datetime = origination_destination['segments'][0]['departureDateTime'].split('.000')[0][:-3]
                departure_date = departure_datetime.split('T')[0]
                arrival_datetime = origination_destination['segments'][-1]['arrivalDateTime'].split('.000')[0][:-3]

                origin_airport = origination_destination['segments'][0]['originationAirportCode']
                destination_airport = origination_destination['segments'][-1]['destinationAirportCode']
                available = southwest.get_available_flights(
                    departure_date,
                    origin_airport,
                    destination_airport
                )

                # Find that the flight that matches the purchased flight
                matching_flight = next(f for f in available['trips'][0]['airProducts'] if f['segments'][0]['departureDateTime'] == departure_datetime and f['segments'][-1]['arrivalDateTime'] == arrival_datetime)
                matching_flight_price = matching_flight['fareProducts'][-1]['currencyPrice']['discountedTotalFareCents']
                matching_flights_price += matching_flight_price

            matching_flights_price = matching_flights_price / 100.00
            # Calculate refund details (current flight price - sum(current price of all legs), and print log message
            refund_amount = itinerary_price - matching_flights_price
            message = '{base_message} detected for itinerary {record_locator} from {origin_airport} to {destination_airport} returning on {departure_date}'.format(
                base_message='Price drop of ${0:.2f}'.format(refund_amount) if refund_amount > 0 else 'Price increase of ${0:.2f}'.format(refund_amount * -1),
                refund_amount=refund_amount,
                record_locator=record_locator,
                origin_airport=origin_airport,
                destination_airport=destination_airport,
                departure_date=departure_date
            )
            logging.info(message)
            if refund_amount > 0:
                logging.info('Sending email for price drop')
                resp = requests.post(
                    'https://api.mailgun.net/v3/{}/messages'.format(settings.mailgun_domain),
                    auth=('api', settings.mailgun_api_key),
                    data={'from': 'Southwest Alerts <southwest-alerts@{}>'.format(settings.mailgun_domain),
                          'to': [email],
                          'subject': 'Southwest Price Drop Alert',
                          'text': message})
                assert resp.status_code == 200


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    for user in settings.users:
        check_for_price_drops(user.username, user.password, user.email)
