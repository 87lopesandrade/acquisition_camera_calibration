import cv2
import numpy as np

try:
    import PySpin
except ImportError:
    PySpin = None
    print("Aviso: PySpin não encontrado. Rode na Jetson Nano ou mock da câmera será usado caso deseje testar.")

class CameraManager:
    def __init__(self):
        self.system = None
        self.cam_list = None
        self.cam = None
        self.is_streaming = False

    def connect(self):
        if PySpin is None:
            return False, "PySpin não instalado."

        self.system = PySpin.System.GetInstance()
        self.cam_list = self.system.GetCameras()
        
        num_cameras = self.cam_list.GetSize()
        if num_cameras == 0:
            self.cam_list.Clear()
            self.system.ReleaseInstance()
            return False, "Nenhuma câmera conectada."

        # Pegar a primeira câmera
        self.cam = self.cam_list.GetByIndex(0)
        self.cam.Init()
        
        return True, "Câmera conectada com sucesso."

    def start_stream(self):
        if not self.cam:
            return False
        
        # Configurar aquisição para contínuo
        node_acquisition_mode = PySpin.CEnumerationPtr(self.cam.GetNodeMap().GetNode('AcquisitionMode'))
        if PySpin.IsAvailable(node_acquisition_mode) and PySpin.IsWritable(node_acquisition_mode):
            node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
            if PySpin.IsAvailable(node_acquisition_mode_continuous) and PySpin.IsReadable(node_acquisition_mode_continuous):
                node_acquisition_mode.SetIntValue(node_acquisition_mode_continuous.GetValue())

        self.cam.BeginAcquisition()
        self.is_streaming = True
        return True

    def stop_stream(self):
        if self.cam and self.is_streaming:
            try:
                self.cam.EndAcquisition()
            except Exception as ex:
                print(f"Erro ao parar aquisição: {ex}")
            finally:
                self.is_streaming = False

    def disconnect(self):
        self.stop_stream()
        if self.cam:
            try:
                self.cam.DeInit()
            except Exception as ex:
                print(f"Erro ao desinicializar a câmera: {ex}")
            finally:
                del self.cam
                self.cam = None
        if self.cam_list:
            self.cam_list.Clear()
            self.cam_list = None
        if self.system:
            self.system.ReleaseInstance()
            self.system = None

    def get_frame(self):
        """Retorna a imagem atual como um numpy array no formato BGR para OpenCV"""
        if not self.cam or not self.is_streaming:
            return None
        
        try:
            image_result = self.cam.GetNextImage(1000)
            if image_result.IsIncomplete():
                image_result.Release()
                return None

            # Converte para ndarray e muda de RGB/Bayer para BGR se necessário
            # A câmera FLIR normalmente retorna Bayer ou Mono
            image_converted = image_result.Convert(PySpin.PixelFormat_BGR8, PySpin.HQ_LINEAR)
            img_array = image_converted.GetNDArray()
            image_result.Release()
            return img_array
        except PySpin.SpinnakerException as ex:
            print(f"Erro ao capturar frame: {ex}")
            return None

    # --- FUNÇÕES DE CONTROLE (Gain, Exposure, Gamma, Black Balance, White Balance) ---

    def set_exposure(self, value):
        if not self.cam: return
        try:
            # Desabilitar auto-exposure primeiro
            node_exp_auto = PySpin.CEnumerationPtr(self.cam.GetNodeMap().GetNode('ExposureAuto'))
            if PySpin.IsAvailable(node_exp_auto) and PySpin.IsWritable(node_exp_auto):
                node_exp_auto.SetIntValue(node_exp_auto.GetEntryByName('Off').GetValue())

            node_exp = PySpin.CFloatPtr(self.cam.GetNodeMap().GetNode('ExposureTime'))
            if PySpin.IsAvailable(node_exp) and PySpin.IsWritable(node_exp):
                # Garantir que está dentro dos limites
                val = max(node_exp.GetMin(), min(node_exp.GetMax(), value))
                node_exp.SetValue(val)
        except Exception as e:
            print("Erro setando exposição:", e)

    def set_gain(self, value):
        if not self.cam: return
        try:
            node_gain_auto = PySpin.CEnumerationPtr(self.cam.GetNodeMap().GetNode('GainAuto'))
            if PySpin.IsAvailable(node_gain_auto) and PySpin.IsWritable(node_gain_auto):
                node_gain_auto.SetIntValue(node_gain_auto.GetEntryByName('Off').GetValue())
            
            node_gain = PySpin.CFloatPtr(self.cam.GetNodeMap().GetNode('Gain'))
            if PySpin.IsAvailable(node_gain) and PySpin.IsWritable(node_gain):
                val = max(node_gain.GetMin(), min(node_gain.GetMax(), value))
                node_gain.SetValue(val)
        except Exception as e:
            print("Erro setando ganho:", e)

    def set_gamma(self, value):
        if not self.cam: return
        try:
            node_gamma_enable = PySpin.CBooleanPtr(self.cam.GetNodeMap().GetNode('GammaEnable'))
            if PySpin.IsAvailable(node_gamma_enable) and PySpin.IsWritable(node_gamma_enable):
                node_gamma_enable.SetValue(True)

            node_gamma = PySpin.CFloatPtr(self.cam.GetNodeMap().GetNode('Gamma'))
            if PySpin.IsAvailable(node_gamma) and PySpin.IsWritable(node_gamma):
                val = max(node_gamma.GetMin(), min(node_gamma.GetMax(), value))
                node_gamma.SetValue(val)
        except Exception as e:
            print("Erro setando gamma:", e)

    def set_black_level(self, value):
        if not self.cam: return
        try:
            node_bl = PySpin.CFloatPtr(self.cam.GetNodeMap().GetNode('BlackLevel'))
            if PySpin.IsAvailable(node_bl) and PySpin.IsWritable(node_bl):
                val = max(node_bl.GetMin(), min(node_bl.GetMax(), value))
                node_bl.SetValue(val)
        except Exception as e:
            print("Erro setando black level:", e)

    def set_white_balance_auto(self, enable=True):
        if not self.cam: return
        try:
            node_wb_auto = PySpin.CEnumerationPtr(self.cam.GetNodeMap().GetNode('BalanceWhiteAuto'))
            if PySpin.IsAvailable(node_wb_auto) and PySpin.IsWritable(node_wb_auto):
                mode = 'Continuous' if enable else 'Off'
                node_wb_auto.SetIntValue(node_wb_auto.GetEntryByName(mode).GetValue())
        except Exception as e:
            print("Erro setando auto white balance:", e)
