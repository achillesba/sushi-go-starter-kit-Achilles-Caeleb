#!/usr/bin/env python3
"""
Sushi Go Client - Python Starter Kit

This client connects to the Sushi Go server and plays using a simple strategy.
Modify the `choose_card` method to implement your own AI!

Usage:
    python sushi_go_client.py <server_host> <server_port> <game_id> <player_name>

Example:
    python sushi_go_client.py localhost 7878 abc123 MyBot
"""

import random
import re
import socket
import sys
from dataclasses import dataclass
from typing import Optional

# Card names used by the protocol (now using full names instead of codes)
CARD_NAMES = {
    "Tempura": "Tempura",
    "Sashimi": "Sashimi",
    "Dumpling": "Dumpling",
    "Maki Roll (1)": "Maki Roll (1)",
    "Maki Roll (2)": "Maki Roll (2)",
    "Maki Roll (3)": "Maki Roll (3)",
    "Egg Nigiri": "Egg Nigiri",
    "Salmon Nigiri": "Salmon Nigiri",
    "Squid Nigiri": "Squid Nigiri",
    "Pudding": "Pudding",
    "Wasabi": "Wasabi",
    "Chopsticks": "Chopsticks",
}


@dataclass
class GameState:
    """Tracks the current state of the game."""

    game_id: str
    player_id: int
    hand: list[str]
    starting_hand_size: int = 0
    round: int = 1
    turn: int = 1
    P2_game_id: str = None
    P3_game_id: str = None
    P4_game_id: str = None  
    P5_game_id: str = None
    P2_played_cards: list[str] = None
    P3_played_cards: list[str] = None
    P4_played_cards: list[str] = None
    P5_played_cards: list[str] = None
    played_cards: list[str] = None 
    important_cards = {"Dumpling": 0, "Sashimi": 0, "Tempura": 0, "Pudding": 0}
    has_chopsticks: bool = False
    has_unused_wasabi: bool = False

    def __post_init__(self):
        if self.played_cards is None:
            self.played_cards = []


class SushiGoClient:
    """A client for playing Sushi Go."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.state: Optional[GameState] = None
        self._recv_buffer = ""

    def connect(self):
        """Connect to the server."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self._recv_buffer = ""
        print(f"Connected to {self.host}:{self.port}")

    def disconnect(self):
        """Disconnect from the server."""
        if self.sock:
            self.sock.close()
            self.sock = None

    def send(self, command: str):
        """Send a command to the server."""
        message = command + "\n"
        self.sock.sendall(message.encode("utf-8"))
        print(f">>> {command}")

    def receive(self) -> str:
        """Receive one line-delimited message from the server."""
        while True:
            if "\n" in self._recv_buffer:
                line, self._recv_buffer = self._recv_buffer.split("\n", 1)
                message = line.strip()
                print(f"<<< {message}")
                return message

            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Server closed connection")
            self._recv_buffer += chunk.decode("utf-8", errors="replace")

    def receive_until(self, predicate) -> str:
        """Read lines until one matches predicate."""
        while True:
            message = self.receive()
            if not message:
                continue
            if predicate(message):
                return message

    def join_game(self, game_id: str, player_name: str) -> bool:
        """Join a game."""
        self.send(f"JOIN {game_id} {player_name}")
        response = self.receive_until(
            lambda line: line.startswith("WELCOME") or line.startswith("ERROR")
        )

        if response.startswith("WELCOME"):
            parts = response.split()
            self.state = GameState(game_id=parts[1], player_id=int(parts[2]), hand=[])
            return True
        elif response.startswith("ERROR"):
            print(f"Failed to join: {response}")
            return False
        return False

    def signal_ready(self):
        """Signal that we're ready to start."""
        self.send("READY")
        return self.receive()

    def play_card(self, card_index: int):
        """Play a card by index."""
        self.send(f"PLAY {card_index}")
        # REMOVED the return self.receive() here

    def play_chopsticks(self, index1: int, index2: int):
        """Use chopsticks to play two cards."""
        self.send(f"CHOPSTICKS {index1} {index2}")
        # REMOVED the return self.receive() here

    def parse_hand(self, message: str):
        """Parse a HAND message and update state."""
        if message.startswith("HAND"):
            payload = message[len("HAND ") :]
            cards = []
            for match in re.finditer(r"(\d+):(.*?)(?=\s\d+:|$)", payload):
                cards.append(match.group(2).strip())
            if self.state:
                # DETECT NEW ROUND: If the incoming hand is bigger than our current hand, clear the table!
                if len(cards) > len(self.state.hand):
                    self.state.played_cards = []
                    # Also reset important cards so we don't refuse to draft Dumplings in Round 2
                    self.state.important_cards = {"Dumpling": 0, "Sashimi": 0, "Tempura": 0, "Pudding": self.state.important_cards.get("Pudding", 0)}
                    
                self.state.hand = cards
                
                # Update chopsticks/wasabi tracking based on played cards
                self.state.has_chopsticks = "Chopsticks" in self.state.played_cards
                self.state.has_unused_wasabi = any(
                    c == "Wasabi" for c in self.state.played_cards
                ) and not any(
                    c in ("Egg Nigiri", "Salmon Nigiri", "Squid Nigiri")
                    for c in self.state.played_cards
                )
    
    def have_wasabi_and_nigiri(self, hand: list[str]):
        """Check if hand has wasabi and at least one nigiri."""
        
        if "Wasabi" in hand and "Squid Nigiri" in hand:
            playing = [hand.index("Wasabi"), hand.index("Squid Nigiri")]
            return playing
        if "Wasabi" in hand and "Salmon Nigiri" in hand:
            playing = [hand.index("Wasabi"), hand.index("Salmon Nigiri")]
            return playing
        if "Wasabi" in hand and "Egg Nigiri" in hand:
            playing = [hand.index("Wasabi"), hand.index("Egg Nigiri")]
            return playing
        return []

    def have_set(self, hand: list[str]):
        """Check if hand has at least count of card_name."""
        has_set = []
        set_cards = ["Dumpling", "Sashimi", "Tempura"]
        for card in set_cards:
            count = 0
            for i in range(len(hand)):
                if hand[i] == card:
                    count += 1
            if count >= 2:
                has_set.append(card)
        return has_set


    def choose_card(self, hand: list[str]) -> int:
        """
        Choose which card to play.

        This is where you implement your AI strategy!
        The default implementation uses a simple priority-based approach.

        Args:
            hand: List of card codes in your current hand

        Returns:
            Index of the card to play (0-based)
        
        # Simple priority-based strategy
        priority = [
            "Squid Nigiri",  # 3 points, or 9 with wasabi
            "Salmon Nigiri",  # 2 points, or 6 with wasabi
            "Maki Roll (3)",  # 3 maki rolls
            "Maki Roll (2)",  # 2 maki rolls
            "Tempura",  # 5 points per pair
            "Sashimi",  # 10 points per set of 3
            "Dumpling",  # Increasing value
            "Wasabi",  # Triples next nigiri
            "Egg Nigiri",  # 1 point, or 3 with wasabi
            "Pudding",  # End game scoring
            "Maki Roll (1)",  # 1 maki roll
            "Chopsticks",  # Play 2 cards next turn
        ]


        priority = ["",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",]

        """
         

        if self.state and not self.state.has_unused_wasabi and "Wasabi" in hand and len(hand) > 5:
            return hand.index("Wasabi")

        if self.state and not self.state.has_chopsticks and "Chopsticks" in hand and len(hand) > 5:
            return hand.index("Chopsticks")
 
        # If we have wasabi, prioritize good nigiri if larger hand 
        if self.state and self.state.has_unused_wasabi and len(hand) > 5:
            for nigiri in ["Squid Nigiri", "Salmon Nigiri"]:
                if nigiri in hand:
                    self.state.has_unused_wasabi = False
                    return hand.index(nigiri)
                
        if self.state and self.state.has_unused_wasabi and len(hand) <= 5:
            for nigiri in ["Squid Nigiri", "Salmon Nigiri", "Egg Nigiri"]:
                if nigiri in hand:
                    self.state.has_unused_wasabi = False
                    return hand.index(nigiri)
                
        if self.state and self.state.has_chopsticks:
            Tempura_indexes = [i for i, card in enumerate(hand) if card == "Tempura"]
            Sahimi_indexes = [i for i, card in enumerate(hand) if card == "Sashimi"]
            Dumpling_indexes = [i for i, card in enumerate(hand) if card == "Dumpling"]
            if self.have_wasabi_and_nigiri(hand):
                playing = self.have_wasabi_and_nigiri(hand)
                if len(playing) == 2:
                    return playing
            if self.have_set(hand):
                playing = self.have_set(hand)
                if len(playing) > 0:
                    for name in playing:
                        if name == "Dumpling" and self.state.important_cards["Dumpling"] <= 3:
                            if self.state.important_cards["Dumpling"] == 0 and len(self.state.hand) > (self.state.starting_hand_size)/2:
                                continue
                            self.state.important_cards["Dumpling"] += 2
                            self.state.has_chopsticks = False
                            return Dumpling_indexes[:2]
                        if name == "Sashimi" and self.state.important_cards["Sashimi"] == 0 and len(self.state.hand) > 2*((self.state.starting_hand_size)/3):
                            self.state.important_cards["Sashimi"] += 2
                            self.state.has_chopsticks = False
                            return Sahimi_indexes[:2]
                        if name == "Tempura":
                            self.state.important_cards["Tempura"] += 2
                            self.state.has_chopsticks = False
                            return Tempura_indexes[:2]
                            
        if "Dumpling" in hand and self.state and self.state.important_cards["Dumpling"] <= 4:
            if self.state.important_cards["Dumpling"] == 0 and len(self.state.hand) > (self.state.starting_hand_size)/2:
                pass
            else:
                self.state.important_cards["Dumpling"] += 1
                return hand.index("Dumpling")
        if "Sashimi" in hand and self.state and self.state.important_cards["Sashimi"] == 2:
            self.state.important_cards["Sashimi"] += 1
            return hand.index("Sashimi")
        if "Tempura" in hand and self.state and len(self.state.hand) >= (self.state.starting_hand_size)/2:
            self.state.important_cards["Tempura"] += 1
            if (self.state.important_cards["Tempura"])%2 == 0 and len(self.state.hand) < 4:
                pass
            else:  
                return hand.index("Tempura")
        
        priority = [
            "Squid Nigiri",
            "Salmon Nigiri",
            "Egg Nigiri",
            "Maki Roll (3)",
            "Maki Roll (2)",
            "Maki Roll (1)",
            "Pudding"
            ]

        for card in priority:
            if card in hand:
                if card == "Pudding":
                    self.state.important_cards["Pudding"] += 1
                return hand.index(card)

        # Fallback: random
        return random.randint(0, len(hand) - 1)





    def handle_message(self, message: str):
        """Handle a message from the server."""
        if message.startswith("HAND"):
            self.parse_hand(message)
        elif message.startswith("ROUND_START"):
            parts = message.split()
            if self.state:
                self.state.round = int(parts[1])
                self.state.turn = 1
                self.state.played_cards = []
        elif message.startswith("PLAYED"):
            # Cards were revealed, next turn
            if self.state:
                self.state.turn += 1
        elif message.startswith("ROUND_END"):
            # Round ended
            if self.state:
                self.state.played_cards = []
        elif message.startswith("GAME_END"):
            print("Game over!")
            return False
        elif message.startswith("WAITING"):
            # Our move was accepted, waiting for others
            pass
        return True

    def play_turn(self):
        """Play a single turn."""
        if not self.state or not self.state.hand:
            return

        card_index = self.choose_card(self.state.hand)

        if type(card_index) == list:
            # Handle Chopsticks (two cards)
            self.play_chopsticks(card_index[0], card_index[1])
            
            # Immediately update local state
            self.state.played_cards.extend([self.state.hand[card_index[0]], self.state.hand[card_index[1]]])
            if "Chopsticks" in self.state.played_cards:
                self.state.played_cards.remove("Chopsticks")
            self.state.has_chopsticks = False
        else:
            # Handle standard single card play
            self.play_card(card_index)
            
            # Immediately update local state
            self.state.played_cards.append(self.state.hand[card_index])

    def run(self, game_id: str, player_name: str):
        """Main game loop."""
        try:
            self.connect()

            if not self.join_game(game_id, player_name):
                return

            # Signal ready
            response = self.signal_ready()

            # Main game loop
            running = True
            self.state.starting_hand_size = len(self.state.hand)
            self.state.important_cards = {"Dumpling": 0, "Sashimi": 0, "Tempura": 0, "Pudding": 0}
            while running:
                # Check for incoming messages
                message = self.receive()
                running = self.handle_message(message)

                # If we received our hand, play a card
                if message.startswith("HAND") and self.state and self.state.hand:
                    self.play_turn()

        except KeyboardInterrupt:
            print("\nDisconnecting...")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.disconnect()


def main():
    if len(sys.argv) != 5:
        print("Usage: python sushi_go_client.py <host> <port> <game_id> <player_name>")
        print("Example: python sushi_go_client.py localhost 7878 abc123 MyBot")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    game_id = sys.argv[3]
    player_name = sys.argv[4]

    client = SushiGoClient(host, port)
    client.run(game_id, player_name)


if __name__ == "__main__":
    main()
