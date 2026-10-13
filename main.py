import argparse, time
from src.realtime.pipeline import command_bus, start, shutdown
from src.realtime.simulator import start_simulator

def main():
    parser=argparse.ArgumentParser(description="Gamified stroke rehabilitation research prototype")
    parser.add_argument("mode",nargs="?",choices=["keyboard","sim","vision","live"],default="keyboard")
    parser.add_argument("--game",choices=["balloon","car","treasure","shape"],default="balloon")
    parser.add_argument("--patient",default="P01"); args=parser.parse_args()
    if args.mode=="sim":start_simulator()
    elif args.mode=="vision":start(use_emg=False,use_vision=True,show_preview=False)
    elif args.mode=="live":start(show_preview=False)
    # Open the game immediately in Webcam + EMG mode too. Each game displays
    # a waiting screen and suppresses gameplay until fresh EMG samples and a
    # complete feature window arrive (see BaseGame.wait_for_required_emg).
    time.sleep(.2)
    try:
        if args.game=="balloon":from src.games.balloon_pop import BalloonPop as Game
        elif args.game=="car":from src.games.car_driving import CarDriving as Game
        elif args.game=="treasure":from src.games.treasure_hunt import TreasureHunt as Game
        else:from src.games.shape_matching import ShapeMatching as Game
        game=Game(command_bus,args.patient)
        game.control_mode=args.mode
        print(f"Pygame video driver: {__import__('pygame').display.get_driver()}; window info: {__import__('pygame').display.get_wm_info()}",flush=True)
        print(f"Pygame window created for {args.game}",flush=True)
        game.run()
    except ImportError as e:raise SystemExit(f"Install project dependencies: {e}")
    finally:shutdown()

if __name__=="__main__":main()
