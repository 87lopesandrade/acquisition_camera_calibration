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
        
        # Dicionário de câmeras conectadas: { "serial": cam_obj }
        self.cams = {}
        self.is_streaming = False
        self.processor = None
        
        # Mapeamento de grupos para facilitar o controle
        self.groups = {
            'FPP': ['19337756', '19337638'],
            'DEFL': ['22348163', '22348161']
        }

    def connect(self):
        if PySpin is None:
            return False, "PySpin não instalado."

        self.system = PySpin.System.GetInstance()
        self.cam_list = self.system.GetCameras()
        
        if self.processor is None:
            self.processor = PySpin.ImageProcessor()
            self.processor.SetColorProcessing(PySpin.SPINNAKER_COLOR_PROCESSING_ALGORITHM_HQ_LINEAR)
        
        num_cameras = self.cam_list.GetSize()
        if num_cameras == 0:
            self.cam_list.Clear()
            self.system.ReleaseInstance()
            return False, "Nenhuma câmera conectada."

        self.cams = {}
        
        # Conectar e inicializar todas as câmeras disponíveis
        for i in range(num_cameras):
            cam = self.cam_list.GetByIndex(i)
            cam.Init()
            
            # Obter Serial Number
            node_device_serial_number = PySpin.CStringPtr(cam.GetNodeMap().GetNode('DeviceSerialNumber'))
            if PySpin.IsAvailable(node_device_serial_number) and PySpin.IsReadable(node_device_serial_number):
                serial = node_device_serial_number.GetValue()
            else:
                serial = f"UNKNOWN_{i}"
                
            self.cams[serial] = cam
            
            try:
                # Configurar limite de banda USB (muito importante na Jetson Nano para 4 câmeras)
                node_device_link = PySpin.CIntegerPtr(cam.GetNodeMap().GetNode('DeviceLinkThroughputLimit'))
                if PySpin.IsAvailable(node_device_link) and PySpin.IsWritable(node_device_link):
                    min_val = node_device_link.GetMin()
                    max_val = node_device_link.GetMax()
                    try:
                        inc = node_device_link.GetInc()
                    except:
                        inc = 1
                    target = 80000000
                    if inc > 1:
                        target = min_val + ((target - min_val) // inc) * inc
                    val = max(min_val, min(max_val, target))
                    node_device_link.SetValue(val)
            except Exception as e:
                print(f"Aviso: Não foi possível definir o DeviceLinkThroughputLimit na câmera {serial}: {e}")
        
        return True, f"{len(self.cams)} câmera(s) conectada(s) com sucesso."

    def start_stream(self):
        if not self.cams:
            return False
        
        for serial, cam in self.cams.items():
            # Configurar aquisição para contínuo
            node_acquisition_mode = PySpin.CEnumerationPtr(cam.GetNodeMap().GetNode('AcquisitionMode'))
            if PySpin.IsAvailable(node_acquisition_mode) and PySpin.IsWritable(node_acquisition_mode):
                node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
                if PySpin.IsAvailable(node_acquisition_mode_continuous) and PySpin.IsReadable(node_acquisition_mode_continuous):
                    node_acquisition_mode.SetIntValue(node_acquisition_mode_continuous.GetValue())

            cam.BeginAcquisition()
            
        self.is_streaming = True
        return True

    def stop_stream(self):
        if self.is_streaming:
            for serial, cam in self.cams.items():
                try:
                    cam.EndAcquisition()
                except Exception as ex:
                    print(f"Erro ao parar aquisição da câmera {serial}: {ex}")
            self.is_streaming = False

    def disconnect(self):
        self.stop_stream()
        for serial, cam in self.cams.items():
            try:
                cam.DeInit()
            except Exception as ex:
                print(f"Erro ao desinicializar a câmera {serial}: {ex}")
        self.cams.clear()
        
        if self.processor is not None:
            del self.processor
            self.processor = None
            
        if self.cam_list:
            self.cam_list.Clear()
            self.cam_list = None
        if self.system:
            self.system.ReleaseInstance()
            self.system = None

    def get_frames(self):
        """Retorna um dicionário com os frames de cada câmera {serial: img_array}"""
        if not self.cams or not self.is_streaming:
            return None
        
        frames = {}
        for serial, cam in self.cams.items():
            image_result = None
            try:
                image_result = cam.GetNextImage(1000)
                if image_result.IsIncomplete():
                    frames[serial] = None
                    continue

                if hasattr(image_result, 'Convert'):
                    image_converted = image_result.Convert(PySpin.PixelFormat_BGR8, PySpin.HQ_LINEAR)
                else:
                    image_converted = self.processor.Convert(image_result, PySpin.PixelFormat_BGR8)
                
                img_array = image_converted.GetNDArray().copy()
                frames[serial] = img_array
            except Exception as ex:
                print(f"Erro ao capturar frame da câmera {serial}: {ex}")
                if "[-1002]" in str(ex) or "removed from the list" in str(ex):
                    self.is_streaming = False
                frames[serial] = None
            finally:
                if 'image_converted' in locals():
                    del image_converted
                if image_result is not None:
                    try:
                        image_result.Release()
                    except:
                        pass
                    del image_result
                
        return frames

    # --- FUNÇÕES DE CONTROLE (Gain, Exposure, Gamma, Black Balance, White Balance) ---

    def apply_to_group(self, group, func):
        if group not in self.groups:
            return
        serials = self.groups[group]
        for serial in serials:
            if serial in self.cams:
                func(serial, self.cams[serial])

    def set_exposure(self, group, value):
        def _set(serial, cam):
            try:
                node_exp_auto = PySpin.CEnumerationPtr(cam.GetNodeMap().GetNode('ExposureAuto'))
                if PySpin.IsAvailable(node_exp_auto) and PySpin.IsWritable(node_exp_auto):
                    node_exp_auto.SetIntValue(node_exp_auto.GetEntryByName('Off').GetValue())

                node_exp = PySpin.CFloatPtr(cam.GetNodeMap().GetNode('ExposureTime'))
                if PySpin.IsAvailable(node_exp) and PySpin.IsWritable(node_exp):
                    val = max(node_exp.GetMin(), min(node_exp.GetMax(), value))
                    node_exp.SetValue(val)
            except Exception as e:
                print(f"Erro setando exposição na câmera {serial}:", e)
        self.apply_to_group(group, _set)

    def set_gain(self, group, value):
        def _set(serial, cam):
            try:
                node_gain_auto = PySpin.CEnumerationPtr(cam.GetNodeMap().GetNode('GainAuto'))
                if PySpin.IsAvailable(node_gain_auto) and PySpin.IsWritable(node_gain_auto):
                    node_gain_auto.SetIntValue(node_gain_auto.GetEntryByName('Off').GetValue())
                
                node_gain = PySpin.CFloatPtr(cam.GetNodeMap().GetNode('Gain'))
                if PySpin.IsAvailable(node_gain) and PySpin.IsWritable(node_gain):
                    val = max(node_gain.GetMin(), min(node_gain.GetMax(), value))
                    node_gain.SetValue(val)
            except Exception as e:
                print(f"Erro setando ganho na câmera {serial}:", e)
        self.apply_to_group(group, _set)

    def set_gamma(self, group, value):
        def _set(serial, cam):
            try:
                node_gamma_enable = PySpin.CBooleanPtr(cam.GetNodeMap().GetNode('GammaEnable'))
                if PySpin.IsAvailable(node_gamma_enable) and PySpin.IsWritable(node_gamma_enable):
                    node_gamma_enable.SetValue(True)

                node_gamma = PySpin.CFloatPtr(cam.GetNodeMap().GetNode('Gamma'))
                if PySpin.IsAvailable(node_gamma) and PySpin.IsWritable(node_gamma):
                    val = max(node_gamma.GetMin(), min(node_gamma.GetMax(), value))
                    node_gamma.SetValue(val)
            except Exception as e:
                print(f"Erro setando gamma na câmera {serial}:", e)
        self.apply_to_group(group, _set)

    def set_black_level(self, group, value):
        def _set(serial, cam):
            try:
                node_bl = PySpin.CFloatPtr(cam.GetNodeMap().GetNode('BlackLevel'))
                if PySpin.IsAvailable(node_bl) and PySpin.IsWritable(node_bl):
                    val = max(node_bl.GetMin(), min(node_bl.GetMax(), value))
                    node_bl.SetValue(val)
            except Exception as e:
                print(f"Erro setando black level na câmera {serial}:", e)
        self.apply_to_group(group, _set)

    def set_white_balance_auto(self, group, enable=True):
        def _set(serial, cam):
            try:
                node_wb_auto = PySpin.CEnumerationPtr(cam.GetNodeMap().GetNode('BalanceWhiteAuto'))
                if PySpin.IsAvailable(node_wb_auto) and PySpin.IsWritable(node_wb_auto):
                    mode = 'Continuous' if enable else 'Off'
                    node_wb_auto.SetIntValue(node_wb_auto.GetEntryByName(mode).GetValue())
            except Exception as e:
                print(f"Erro setando auto white balance na câmera {serial}:", e)
        self.apply_to_group(group, _set)
