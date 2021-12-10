using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Text.Json;


namespace Music_Caster_Updater
{
    class Program
    {
        private static void ExtractZip(string fileName)
        {
            /**
             * Extracts fileName (ends with .zip) to root directory
             * Deletes fileName after
             */
            using (ZipArchive archive = ZipFile.OpenRead(fileName))
            {
                foreach (ZipArchiveEntry entry in archive.Entries)
                {
                    string dir = Path.GetDirectoryName(entry.FullName);
                    if (dir != "" && !Directory.Exists(dir)) Directory.CreateDirectory(dir);
                    try
                    {
                        if (File.Exists(entry.FullName)) File.Delete(entry.FullName);
                        entry.ExtractToFile(entry.FullName);
                    }
                    catch (IOException) { }
                    catch (System.UnauthorizedAccessException) { }
                }
            }
            File.Delete(fileName);
        }
        private static void Download(string url, string outfile)
        {
            // Downloads url to outfile
            // If outfile is a zip, extract it
            Debug.WriteLine($"Downloading {outfile}");
            using WebClient myWebClient = new WebClient();
            myWebClient.DownloadFile(url, outfile);
            if (outfile.EndsWith(".zip")) ExtractZip(outfile);
        }

        private static List<string> DirectorySearch(string dir)
        {   // returns all files in a dir and its subdirs recursively
            List<string> files = new List<string>();
            try
            {
                foreach (string f in Directory.GetFiles(dir)) files.Add(Path.GetFileName(f));
                foreach (string d in Directory.GetDirectories(dir)) files.AddRange(DirectorySearch(d));
            }
            catch (Exception) { }
            return files;
        }


        static void Main()
        {
            // use @ for string literals
            const string releasesURL = @"https://api.github.com/repos/elibroftw/music-caster/releases/latest";
            const string settingsFile = "settings.json";
            Directory.SetCurrentDirectory(AppDomain.CurrentDomain.BaseDirectory);  // Change working dir to dir of this program
            Dictionary<string, object> loadedSettings = new Dictionary<string, object>() { { "DEBUG", false } };

            if (File.Exists(settingsFile))
            {
                using StreamReader fs = new StreamReader(settingsFile);
                loadedSettings = JsonSerializer.Deserialize<Dictionary<string, object>>(fs.ReadToEnd());
            }
            bool debugSetting = false;
            try
            {
                debugSetting = ((JsonElement)loadedSettings.GetValueOrDefault("DEBUG")).GetBoolean();
            }
            catch (InvalidCastException) { }


            Dictionary<string, object> jsonResponse;

            HttpWebRequest request = (HttpWebRequest)WebRequest.Create(releasesURL);
            request.Method = "GET";
            request.UserAgent = "MusicCasterUpdaterC#";
            using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
            using (Stream stream = response.GetResponseStream())
            using (StreamReader reader = new StreamReader(stream))
            {
                jsonResponse = JsonSerializer.Deserialize<Dictionary<string, object>>((new StreamReader(response.GetResponseStream())).ReadToEnd());
            }

            string setupDownloadURL = "", portableDownloadURL = "";

            JsonElement assets = (JsonElement) jsonResponse.GetValueOrDefault("assets");
            foreach (JsonElement asset in assets.EnumerateArray())
            {
                if (asset.GetProperty("name").ToString().Contains("exe"))
                    setupDownloadURL = asset.GetProperty("browser_download_url").ToString();
                else if (asset.GetProperty("name").ToString().ToLower().Contains("portable"))
                    portableDownloadURL = asset.GetProperty("browser_download_url").ToString();
            }
            if (debugSetting)
            {
                string latestVersion = jsonResponse.GetValueOrDefault("tag_name").ToString();
                Debug.WriteLine($"Latest Version: {latestVersion}");
                Debug.WriteLine($"Portable:       {portableDownloadURL}");
                Debug.WriteLine($"Installer:      {setupDownloadURL}");
            }
            else if (File.Exists("unins000.exe"))
            {   // Was installed using the Installer
                Download(setupDownloadURL, "MC_Installer.exe");
                Process.Start("MC_Installer.exe", "/VERYSILENT /CLOSEAPPLICATIONS /FORCECLOSEAPPLICATIONS /MERGETASKS=\"!desktopicon\"");
            }
            else
            {   // portable installation
                Download(portableDownloadURL, "Portable.zip");
                Process.Start("\"Music Caster.exe\" --nupdate");
            }
        }
    }
}
