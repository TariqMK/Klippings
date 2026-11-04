# README

_**Disclaimer:** Most if not all of the code here has been written in Python with the help of AI_

---

![klippings_logo_v6](https://github.com/user-attachments/assets/5ce2ea13-acf9-4781-9b3d-4fdb4e93fa4d)

## What is Klippings?

Klippings is a Kindle Highlight Processor aimed for use with Kindle's `My Clippings.txt` file, where book highlights for (sideloaded) documents reside.

Klippings exists to aid anyone who wishes for more granular control over their highlights and to be able to export and store them in an organised, systematic manner.

Your original `My Clippings.txt` file is not amended in any way.

---

## How Does it Work?

The highlights contained within `My Clippings.txt` contain entries from all the sideloaded books one has read on the Kindle device. For long term flexibility this is both inefficient and prone to data corruption and loss, especially over time as the file size grows ever larger.

Klippings takes `My Clippings.txt` as the input, scans it for all highlights, recognises if there are multiple books and then outputs a text file per book containing all related highlights.

<img width="1101" height="219" alt="image" src="https://github.com/user-attachments/assets/c3a91832-15f2-44ee-b841-b6e987cfa3c4" />

The option to output highlights with or without metadata is available, as illustrated in the screenshots below.

## Screenshots

User Interface:

<img width="1354" height="1993" alt="image" src="https://github.com/user-attachments/assets/c407faa6-8d8d-44bb-bc28-085ef3dd92b9" />

Standard Export (Sample):

<img width="1036" height="1065" alt="image" src="https://github.com/user-attachments/assets/c6d55e20-c3c9-4cb8-86f8-9beb44296793" />

Simplified Export (Sample):

<img width="1037" height="1065" alt="image" src="https://github.com/user-attachments/assets/5daba761-894c-4dc4-822b-67b6a70df817" />

---

## Run Directly

Download the latest version for Windows, macOS (Apple Silicon) or Linux from the [Releases](https://github.com/TariqMK/Klippings/releases) Page and run it.

The macOS app is unsigned, so the first time you open it you will need to approve it under System Settings > Privacy & Security.

All required folders will be automatically created wherever you specify. 

Enjoy!

## Run From Source

Install the project and its required libraries from the repository root:

```
pip install .
```

Then simply run the command below to bring up the GUI:

```
klippings
```

All required folders will be automatically created. Enjoy!

To run the tests:

```
pip install ".[dev]"
pytest
```

---

## Creating a Release

Run the **Release** workflow from the repository's Actions tab, on `main`, and choose:

- **Release type:** `draft` or `public`
- **Version increment:** `patch`, `minor` or `major`

The new version is worked out from the highest existing tag or release, including drafts. It is then shown in the application and used to tag the release.

---

## Notes

- The new text files for each related book will be placed in a new folder in the specified directory named `Highlights_by_Book`. If this folder does not exist, it will be created
- You also have the option to strip the page location metadata and have your highlights stored cleanly for PKMS systems like Obsidian
- When the application is run and the highlights have been extracted, a summary of books and highlights processed will be displayed in the application itself
- Bookmarks, notes, article clips, empty highlights, clipping limit messages and exact duplicates are left out of the export, and the application shows how many of each were skipped
- Running the application again overwrites the existing files for the selected books

---

**Known Issues:**

- Over the years, Amazon has slightly changed the syntax of highlight metadata within `My Clippings.txt`. The common English formats are supported, but `My Clippings.txt` files from Kindles set to other languages are not yet, and their entries are counted as unrecognised. If you experience any problems, please raise an issue and I will look into it
- A book with no author whose title ends in brackets, such as `Book (Vol 1)`, will show `Vol 1` as its author, as the file format doesn't distinguish the two
- If you extend an existing highlight on your Kindle, both the old and new versions are kept, as Kindle records them as separate highlights
