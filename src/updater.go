package main

import (
	"archive/zip"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/ioutil"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

func loadSettings() map[string]interface{} {
	settingsFile := "settings.json"
	loadedSettings := map[string]interface{}{"DEBUG": false}
	jsonFile, err := os.Open(settingsFile)
	if err == nil {
		byteValue, err := ioutil.ReadAll(jsonFile)
		if err == nil {
			json.Unmarshal(byteValue, &loadedSettings)
		}
	}
	return loadedSettings
}

func main() {
	releasesURL := "https://api.github.com/repos/elibroftw/music-caster/releases/latest"
	ex, _ := os.Executable()
	os.Chdir(filepath.Dir(ex))
	// load settings

	client := http.Client{Timeout: time.Second * 5}
	req, _ := http.NewRequest(http.MethodGet, releasesURL, nil)

	res, err := client.Do(req)
	if err != nil {
		fmt.Println("Failed to make request", err)
		return
	}

	if res.Body != nil {
		defer res.Body.Close()
	}

	body, err := ioutil.ReadAll(res.Body)

	if err == nil {
		var jsonResponse map[string]interface{}
		if json.Unmarshal(body, &jsonResponse) == nil {
			// if json parsing successful
			var setupDownloadURL, portableDownloadURL string
			assets := jsonResponse["assets"].([]interface{})
			for _, v := range assets {
				asset := v.(map[string]interface{})
				if strings.HasSuffix(asset["name"].(string), ".exe") {
					setupDownloadURL = asset["browser_download_url"].(string)
				} else if strings.Contains(strings.ToLower(asset["name"].(string)), "portable") {
					portableDownloadURL = asset["browser_download_url"].(string)
				}
			}

			fmt.Println("Latest Version:", jsonResponse["tag_name"].(string))
			fmt.Println("Installer:      ", setupDownloadURL)
			fmt.Println("Portable:      ", portableDownloadURL)

			loadedSettings := loadSettings()
			if debugSetting, ok := loadedSettings["DEBUG"].(bool); ok && debugSetting {
				// don't download anything
				return
			}

			file, err := os.Open("unins000.exe")
			file.Close()
			if errors.Is(err, os.ErrNotExist) { // portable or linux? installation
				// TODO: Linux support
				download(portableDownloadURL, "Portable.zip")
				exec.Command("Music Caster", "--nupdate").Start()
			} else {
				// installer exists
				download(setupDownloadURL, "MC_Installer.exe")
				exec.Command("MC_Installer.exe", `/VERYSILENT /CLOSEAPPLICATIONS /FORCECLOSEAPPLICATIONS /MERGETASKS="!desktopicon"`)
			}
		}
	}

}

func extractZip(src string) error {
	// https://golangcode.com/unzip-files-in-go/
	var filenames []string

	r, err := zip.OpenReader(src)
	if err != nil {
		return err
	}
	defer r.Close()

	src, _ = filepath.Abs(src)
	dest := filepath.Dir(src)
	fmt.Println("Extracting", src, "to", dest)
	for _, f := range r.File {

		// Store filename/path for returning and using later on
		fpath := filepath.Join(dest, f.Name)

		// Check for ZipSlip. More Info: http://bit.ly/2MsjAWE
		if !strings.HasPrefix(fpath, filepath.Clean(dest)+string(os.PathSeparator)) {
			return fmt.Errorf("%s: illegal file path", fpath)
		}

		filenames = append(filenames, fpath)

		if f.FileInfo().IsDir() {
			// Make Folder
			os.MkdirAll(fpath, os.ModePerm)
			continue
		}

		// Make File
		if err = os.MkdirAll(filepath.Dir(fpath), os.ModePerm); err != nil {
			return err
		}

		outFile, err := os.OpenFile(fpath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, f.Mode())
		if err == nil {
			rc, err := f.Open()
			if err != nil {
				return err
			}

			_, err = io.Copy(outFile, rc)

			// Close the file without defer to close before next iteration of loop
			outFile.Close()
			rc.Close()

			if err != nil {
				return err
			}
		}
	}
	// delete file
    r.Close()
	err = os.Remove(src)
	return err
}

func download(url string, filepath string) {
	// https://golangcode.com/download-a-file-from-a-url/
	fmt.Println("Downloading", filepath)

	resp, err := http.Get(url)
	if err != nil {
		return
	}
	defer resp.Body.Close()

	// Create the file
	out, err := os.Create(filepath)
	if err != nil {
		return
	}

	// Write the body to file
	_, err = io.Copy(out, resp.Body)
    out.Close()
	if err != nil {
		panic(err)
	}

	if strings.HasSuffix(filepath, ".zip") {
		extractZip(filepath)
	}
}

// go build -ldflags "-w -s"
