import cv2
import numpy as np
import json
import os

class CalibrationManager:
    def __init__(self):
        # Parametros padrão do tabuleiro informados
        self.squares_x = 11
        self.squares_y = 8
        self.square_length = 30.0  # 30 mm (valor padrão, deve ser alterado via UI)
        self.marker_length = 23.0  # 23 mm (valor padrão)
        
        # O dicionário informado é o 5X5. Vamos usar o de 50.
        self.dictionary = cv2.aruco.Dictionary_get(cv2.aruco.DICT_5X5_50) if hasattr(cv2.aruco, 'Dictionary_get') else cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50)
        
        self.board = None
        self.update_board_params(self.square_length, self.marker_length)

        # Armazenar pontos adquiridos
        self.all_corners = []
        self.all_ids = []
        self.image_size = None
        
        self.line_y_ratio = 0.5  # Posição da linha vermelha (0.0 a 1.0)

    def update_board_params(self, square_length, marker_length):
        self.square_length = square_length
        self.marker_length = marker_length
        
        # Compatibilidade com OpenCV mais antigo (JetPack 4.x) vs novo (OpenCV 4.7+)
        if hasattr(cv2.aruco, 'CharucoBoard_create'):
            self.board = cv2.aruco.CharucoBoard_create(
                self.squares_x, self.squares_y, 
                self.square_length, self.marker_length, 
                self.dictionary
            )
        else:
            self.board = cv2.aruco.CharucoBoard(
                (self.squares_x, self.squares_y),
                self.square_length, self.marker_length, 
                self.dictionary
            )

    def process_frame(self, frame):
        """
        Recebe um frame, detecta o ChArUco e retorna o frame desenhado, 
        além dos cantos/ids encontrados para possível captura.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.image_size is None:
            self.image_size = gray.shape[::-1]

        # Detectar marcadores ArUco
        if hasattr(cv2.aruco, 'detectMarkers'):
            corners, ids, rejected = cv2.aruco.detectMarkers(gray, self.dictionary)
        else:
            detector = cv2.aruco.ArucoDetector(self.dictionary)
            corners, ids, rejected = detector.detectMarkers(gray)

        display_frame = frame.copy()
        charuco_corners, charuco_ids = None, None

        if ids is not None and len(ids) > 0:
            cv2.aruco.drawDetectedMarkers(display_frame, corners, ids)
            
            # Interpolar cantos do ChArUco
            if hasattr(cv2.aruco, 'interpolateCornersCharuco'):
                retval, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
                    corners, ids, gray, self.board)
            else:
                retval, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
                    corners, ids, gray, self.board)

            if retval > 0:
                cv2.aruco.drawDetectedCornersCharuco(display_frame, charuco_corners, charuco_ids, (0, 255, 0))

        # --- Adicionar linha vermelha e extrair perfil ---
        H, W = display_frame.shape[:2]
        line_y = int(self.line_y_ratio * (H - 1))
        
        # Desenhar linha vermelha horizontal
        cv2.line(display_frame, (0, line_y), (W, line_y), (0, 0, 255), 2)
        
        # Extrair perfil de intensidade
        profile = gray[line_y, :]
        # ------------------------------------------------

        return display_frame, charuco_corners, charuco_ids, profile

    def add_capture(self, charuco_corners, charuco_ids):
        if charuco_corners is not None and charuco_ids is not None and len(charuco_corners) >= 4:
            self.all_corners.append(charuco_corners)
            self.all_ids.append(charuco_ids)
            return True
        return False

    def clear_captures(self):
        self.all_corners = []
        self.all_ids = []

    def calibrate(self):
        if len(self.all_corners) < 5:
            return False, "Poucas capturas. Recomenda-se no mínimo 10 posições diferentes."

        print(f"Iniciando calibração com {len(self.all_corners)} poses...")
        try:
            # Compatibilidade da API
            if hasattr(cv2.aruco, 'calibrateCameraCharuco'):
                retval, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.aruco.calibrateCameraCharuco(
                    self.all_corners, self.all_ids, self.board, self.image_size, None, None)
            else:
                retval, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.aruco.calibrateCameraCharuco(
                    self.all_corners, self.all_ids, self.board, self.image_size, None, None)

            return True, {
                "rms": retval,
                "camera_matrix": camera_matrix,
                "dist_coeffs": dist_coeffs
            }
        except Exception as e:
            return False, f"Erro na calibração: {e}"

    def save_calibration(self, calibration_data, save_dir="."):
        # Extrai os dados
        cam_matrix = calibration_data["camera_matrix"]
        dist_coeffs = calibration_data["dist_coeffs"]
        rms = calibration_data["rms"]

        # 1. Salvar como NPY
        np.save(os.path.join(save_dir, "camera_matrix.npy"), cam_matrix)
        np.save(os.path.join(save_dir, "dist_coeffs.npy"), dist_coeffs)

        # 2. Salvar como JSON
        json_data = {
            "rms_error": float(rms),
            "camera_matrix": cam_matrix.tolist(),
            "dist_coeffs": dist_coeffs.tolist()
        }
        with open(os.path.join(save_dir, "calibration_params.json"), "w") as f:
            json.dump(json_data, f, indent=4)
            
        return os.path.join(save_dir, "calibration_params.json")
