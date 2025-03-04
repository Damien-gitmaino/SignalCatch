import yfinance as yf
import json


def load_config(file_path):
    """
    Charge le fichier de configuration JSON.
    """
    with open(file_path, 'r') as file:
        return json.load(file)


def fetch_data(tickers, period, interval='1d'):
    """
    Récupère les données historiques des tickers pour une période donnée.

    :param tickers: Liste de tickers à récupérer.
    :param period: Période (ex. '1mo', '3mo', '1y').
    :param interval: Intervalle des données (ex. '1d', '1h').
    :return: Un dictionnaire avec les tickers comme clés et les DataFrames comme valeurs.
    """
    data = {}
    for ticker in tickers:
        try:
            print(f"Fetching data for {ticker}...")
            df = yf.download(ticker, period=period, interval=interval, progress=False)
            data[ticker] = df
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")
    return data


def save_data(data, output_dir):
    """
    Sauvegarde les données dans des fichiers CSV.

    :param data: Dictionnaire contenant les DataFrames.
    :param output_dir: Répertoire où les fichiers seront sauvegardés.
    """
    for ticker, df in data.items():
        output_path = f"{output_dir}/{ticker}.csv"
        df.to_csv(output_path)
        print(f"Data for {ticker} saved to {output_path}")


def main(config_path, output_dir):
    """
    Programme principal.

    :param config_path: Chemin vers le fichier de configuration.
    :param output_dir: Répertoire de sortie pour les fichiers CSV.
    """
    config = load_config(config_path)
    tickers = config.get("tickers", [])
    period = config.get("period", "1mo")
    interval = config.get("interval", "1d")

    if not tickers:
        print("No tickers found in the configuration file.")
        return

    data = fetch_data(tickers, period, interval)
    save_data(data, output_dir)
    print("Data fetching and saving completed.")


if __name__ == "__main__":
    # Chemin vers le fichier de configuration et dossier de sortie
    config_file_path = "config.json"
    output_directory = "data"

    main(config_file_path, output_directory)