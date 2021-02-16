import socket
import threading
import multiprocessing
import sys
import lxml  # this is required for line 30 to run (even though the import seems unused)
import pandas as pd
from selenium import webdriver
from bs4 import BeautifulSoup


# User must edit CHROMEDRIVER_PATH, BINARY_LOCATION and SITE_TO_SCRAPE appropriately
HOST = "localhost"
PORT = 8080
CHROMEDRIVER_PATH = "/usr/bin/chromedriver"
BINARY_LOCATION = "/usr/bin/google-chrome"
SITE_TO_SCRAPE = ""


# Update Process functions:
def start_webdriver():
    options = webdriver.ChromeOptions()
    options.binary_location = BINARY_LOCATION
    options.headless = True
    driver = webdriver.Chrome(CHROMEDRIVER_PATH, options=options)
    driver.get(SITE_TO_SCRAPE)
    cookie_consent = driver.find_element_by_name("agree")
    cookie_consent.click()
    return driver


def get_rates(browser):
    soup = BeautifulSoup(browser.execute_script("return document.documentElement.outerHTML"), 'lxml')
    table = soup.find('table')
    df = pd.read_html(str(table))[0]
    # df now contains the data of the first table element on SITE_TO_SCRAPE
    # The following two lines will need to be adapted to scrape data specific to the chosen SITE_TO_SCRAPE
    df['Name'] = list(map(lambda x: x.replace("/", ":"), df['Name']))
    rate_dict = df.set_index('Name').to_dict()['Last price']
    return rate_dict


def update_handler(shared_dict, ready_for_clients):
    browser = start_webdriver()
    exchange_rates = get_rates(browser)
    for key in exchange_rates:
        shared_dict[key] = exchange_rates[key]
    ready_for_clients.set()
    while True:
        rate_dict = get_rates(browser)
        ready_for_clients.clear()
        for key in rate_dict:
            shared_dict[key] = rate_dict[key]
        ready_for_clients.set()


# Client Process functions:
def send_string(conn, string: str):
    conn.sendall((string + '\n').encode())


def client_handler(shared_dict, ready_for_clients):
    ready_for_clients.wait()  # This prevent clients from connecting before the server is ready
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen()
    print("Ready for client connections")
    while True:
        conn, addr = s.accept()
        x = threading.Thread(target=client, args=(conn, addr, shared_dict, ready_for_clients))
        x.start()


def client(conn, addr, shared_dict, ready_for_clients):
    try:
        with conn:
            print('Connected by', addr)
            while True:
                req = conn.recv(4096).decode().strip()
                ready_for_clients.wait()
                if str(req) not in shared_dict:
                    send_string(conn, str(req))
                    send_string(conn, "Bad Request")
                    send_string(conn, "Please send a dictionary key in the format: '***:***'")

                else:
                    rate = shared_dict[req]
                    send_string(conn, str(rate))
    except ConnectionResetError:
        print("Connection reset/closed by client", addr)
        sys.exit()


if __name__ == "__main__":

    try:
        multiprocessing.set_start_method('fork')
    except RuntimeError:
        print("RuntimeError encountered when setting multiprocessing start method")

    ready_for_clients = multiprocessing.Event()
    manager = multiprocessing.Manager()
    shared_dict = manager.dict()

    update_process = multiprocessing.Process(target=update_handler,
                                             args=(shared_dict,
                                                   ready_for_clients))
    client_process = multiprocessing.Process(target=client_handler,
                                             args=(shared_dict,
                                                   ready_for_clients))

    update_process.start()
    client_process.start()

    update_process.join()
    client_process.join()
