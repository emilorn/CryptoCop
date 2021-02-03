import json
from os import environ
from time import sleep

import pika
from cardvalidator import luhn


def get_connection_string():
    with open('./config/mb.%s.json' % environ.get('PYTHON_ENV'), 'r') as f:
        return json.load(f)


def connect_to_mb():
    error = False
    connection_string = get_connection_string()
    while not error:
        try:
            credentials = pika.PlainCredentials(connection_string['user'], connection_string['password'])
            connection = pika.BlockingConnection(pika.ConnectionParameters(connection_string['host'], 5672,
                                                                           connection_string['virtualhost'],
                                                                           credentials))
            channel = connection.channel()
            print("connected to " + connection_string['host'])
            return channel, connection
        except:
            sleep(5)
            continue

channel, connection = connect_to_mb()
exchange_name = 'cryptoCopExchange'
create_order_routing_key = 'create-order'
payment_queue_name = 'payment-queue'

# Declare the exchange, if it doesn't exist
channel.exchange_declare(exchange = exchange_name, exchange_type = 'direct', durable = True)
# Declare the queue, if it doesn't exist
channel.queue_declare(queue = payment_queue_name, durable = True)
# Bind the queue to a specific exchange with a routing key
channel.queue_bind(exchange = exchange_name, queue=payment_queue_name, routing_key=create_order_routing_key)


def verify_creditcard(ch, method, properties, data):
    parsed_msg = json.loads(data)
    credit_card_number = parsed_msg['creditCardDto']['CardNumber']
    result = luhn.is_valid(credit_card_number)
    print("The payment card number is ", end ="")
    if(result):
        print("valid.")
    else:
        print("invalid.")
    ch.basic_ack(delivery_tag=method.delivery_tag)


channel.basic_consume(payment_queue_name, verify_creditcard, auto_ack = False)
channel.start_consuming()
connection.close()
