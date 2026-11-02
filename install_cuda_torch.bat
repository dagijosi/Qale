@echo off
title Install PyTorch CUDA 12.4 for Qalē
echo ========================================================
echo   Qalē - Installing PyTorch with CUDA GPU Support
echo   Target: NVIDIA GPU (CUDA cu124)
echo ========================================================
echo.

set PYTHONHOME=C:\Users\HP Victus\AppData\Local\Programs\Python\Python313
set PATH=C:\Python313;C:\Users\HP Victus\AppData\Local\Programs\Python\Python313\Scripts;%PATH%

echo [1/2] Installing torch, torchvision, torchaudio with CUDA 12.4...
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 --force-reinstall

echo.
echo [2/2] Verifying GPU detection...
python -c "import torch; print('----------------------------------------'); print('PyTorch Version :', torch.__version__); print('CUDA Available  :', torch.cuda.is_available()); print('GPU Device Name :', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU Fallback'); print('----------------------------------------')"

echo.
echo Done! You can now restart Qalē using restart.bat.
pause

