# Troubleshooting

| Problem | Fix |
|---|---|
| macOS: "install_mac.command can't be opened" | Right-click it, choose **Open**, then click **Open**. This happens once for files downloaded from the internet. |
| macOS: the standalone app "is damaged" or "can't be opened" | It is unsigned. Right-click the app, choose **Open**, then **Open**. If that fails, run `xattr -dr com.apple.quarantine "/path/to/TrailBuddy Analyzer.app"` in Terminal. |
| macOS on an Intel Mac | MediaPipe no longer ships Intel-Mac builds. Use an Apple-silicon Mac or Windows. |
| Windows SmartScreen blocks the script or app | Click **More info → Run anyway**. |
| "uv: command not found" | Re-run the install script and answer **y**, or install uv from https://docs.astral.sh/uv/. |
| The app doesn't start from the Desktop icon | macOS: check `logs/app.log (in the TrailBuddy folder)`. If you moved the folder, re-run the install script. |
| "Could not download the pose model" | Internet is needed once. You can also download `pose_landmarker_full.task` from the URL in the message into the `models` folder. |
| "A person was detected in only X% of frames" | Keep the whole body in frame, improve lighting, shorten the interval to the descent, or try the *Heavy* pose model under **Show advanced settings**. |
| Knee angles jump or flip | The far leg may have been mistaken for the near leg. Set **Analysed side** to the leg facing the camera. Check the overlay. |
| Knee moment shows "Unavailable" | You need a scale (pick 2 points, or use height) and detected foot contacts. Check the Events tab. |
| No foot contacts detected | The interval may contain no complete step, or tracking is noisy. Lengthen the interval, or raise the filter cut-off in advanced settings. |
| Clap detection warning or low clarity | Search only the first few seconds (**Search first**), or use manual clap frames. |
| "Recordings do not overlap" | The offset sign or size is wrong. Re-detect, or mark the clap frames manually. |
| Pole marker lost | Use a brighter, more saturated tape colour, avoid similar colours in the background, and annotate the gaps by hand. |
| Excel export fails | Close the workbook if it is already open in Excel, then export again. |
