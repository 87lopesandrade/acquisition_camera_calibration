import sys
from PyQt5.QtWidgets import QApplication
from camera_manager import CameraManager
from calibration_manager import CalibrationManager
from gui import CalibratorGUI

def main():
    app = QApplication(sys.argv)
    
    # Inicializa os managers
    cam_manager = CameraManager()
    
    # Inicializa e exibe a interface passando a CLASSE do CalibrationManager
    gui = CalibratorGUI(cam_manager, CalibrationManager)
    gui.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
