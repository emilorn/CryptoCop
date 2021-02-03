import functools
from os import environ
from time import sleep
import pika
import requests
import json


def get_connection_string():
    with open('./config/mb.%s.json' % environ.get('PYTHON_ENV'), 'r') as f:
        return json.load(f)


def connect_to_mb():
    error = False
    connection_string = get_connection_string()
    while not error:
        try:
            credentials = pika.PlainCredentials(connection_string['user'], connection_string['password'])
            connection = pika.BlockingConnection(pika.ConnectionParameters(connection_string['host'], 5672, connection_string['virtualhost'], credentials))
            channel = connection.channel()
            return channel, connection
        except:
            sleep(5)
            continue


channel, connection = connect_to_mb()
exchange_name = 'cryptoCopExchange'
create_order_routing_key = 'create-order'
email_queue_name = 'email_queue'
email_template = '<style>h2{color:green;}table, th, td {border: 1px solid blue; padding:  0px 15px 0px 15px;} ' \
                 'table{border-collapse: collapse;}</style>' \
                 '<h1>Thank you for shopping at CryptoCop!</h1>' \
                 '<p>We hope you\'re happy with your purchase.</p>'

table_header = '<h3>Products:</h3><table><thead><tr style="background-color: rgba(155, 155, 155, .2);' \
               ' border: 1px solid black; color:blue;">' \
               '<th>Currency</th><th>Unit price</th><th>Quantity</th><th>Row price</th>' \
               '</tr></thead><tbody>%s</tbody></table>'

# Declare the exchange, if it doesn't exist
channel.exchange_declare(exchange=exchange_name, exchange_type='direct', durable=True)
# Declare the queue, if it doesn't exist
channel.queue_declare(queue=email_queue_name, durable=True)
# Bind the queue to a specific exchange with a routing key
channel.queue_bind(exchange=exchange_name, queue=email_queue_name, routing_key=create_order_routing_key)


def send_simple_message(to, subject, body):

    return requests.post(
        "https://api.mailgun.net/v3/sandbox1a8535c8dafd4dbfbb332a42f270566a.mailgun.org/messages",
        auth=("api", "0b7c1053d6f153c259af918de1b3d75a-53c13666-14e5cc8f"),
        data={"from": "Mailgun Sandbox <postmaster@sandbox1a8535c8dafd4dbfbb332a42f270566a.mailgun.org>",
              "to": to,
              "subject": subject,
              "html": body})


def send_order_email(ch, method, properties, data):
    parsed_msg = json.loads(data)

    email = parsed_msg['orderDto']['Email']
    items = parsed_msg['orderDto']['OrderItems']
    person_details = '<h3>Personal information:</h3>' \
                     '<p>Full name: %s</br>' \
                     'House: %s %s</br>' \
                     'City: %s</br>' \
                     'Zip Code: %s</br>' \
                     'Country: %s</br></p>' % (parsed_msg['orderDto']['FullName'], parsed_msg['orderDto']['StreetName'],
                                               parsed_msg['orderDto']['HouseNumber'], parsed_msg['orderDto']['City'],
                                               parsed_msg['orderDto']['ZipCode'], parsed_msg['orderDto']['Country'])
    order_details = '<h2>Order details:</h2>' \
                    '<p> Date of order: %s </br>' \
                    'Total price: %f USD</p>' % (parsed_msg['orderDto']['OrderDate'],
                                             float(parsed_msg['orderDto']['TotalPrice']))
    items_html = ''.join(['<tr><td>%s</td><td>%f USD</td><td>%d</td><td>%f USD</td></tr>' % (
        item['ProductIdentifier'], item['UnitPrice'], item['Quantity'], int(item['Quantity']) * float(item['UnitPrice']))
                          for
                          item in items])
    representation = email_template + person_details + order_details + table_header % items_html
    send_simple_message(email, 'Successful order!', representation)
    ch.basic_ack(delivery_tag=method.delivery_tag)


channel.basic_consume(email_queue_name, send_order_email, auto_ack=False)
channel.start_consuming()
connection.close()
