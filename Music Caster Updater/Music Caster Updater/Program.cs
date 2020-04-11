using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net;

using Newtonsoft.Json;
using HtmlAgilityPack;


namespace Music_Caster_Updater
{
    class Program
    {
        private static void ExtractZip(string fileName)
        {
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
            const string releasesURL = @"https://github.com/elibroftw/music-caster/releases";

            Directory.SetCurrentDirectory(AppDomain.CurrentDomain.BaseDirectory);  // Just in case
            Dictionary<string, object> loadedSettings = new Dictionary<string, object>() { { "DEBUG", false } };

            if (File.Exists("settings.json"))
            {
                using StreamReader r = new StreamReader("settings.json");
                loadedSettings = JsonConvert.DeserializeObject<Dictionary<string, object>>(r.ReadToEnd());
            }
            bool debugSetting = (bool)loadedSettings.GetValueOrDefault("DEBUG", false);

            HtmlWeb web = new HtmlWeb();
            HtmlDocument htmlDoc = web.Load(releasesURL);
            HtmlNode latestEntry = null;
            string latestVersion = null;
            foreach (HtmlNode node in htmlDoc.DocumentNode.SelectNodes("//div[@class='release-entry']"))
            {   // get the latest valid release entry
                string releaseType = node.SelectSingleNode(".//span/a").InnerText;
                if (releaseType == "Latest release")
                {
                    latestVersion = node.SelectSingleNode(".//a[contains(@class, 'muted-link') and contains(@class, 'css-truncate')]").GetAttributeValue("title", "0.0.0").Substring(1);
                    latestEntry = node;
                    break;
                }
            }
            if (latestEntry != null)
            {
                HtmlNode details = latestEntry.SelectSingleNode(".//details[contains(@class, 'details-reset') and contains(@class, 'Details-element')]");
                List<string> downloadLinks = new List<string>();
                foreach (HtmlNode node in details.SelectNodes(".//a"))
                {   // collect download links
                    string url = node.GetAttributeValue("href", "");
                    if (url != "") downloadLinks.Add(url);
                }
                string setupDownloadLink = $"https://github.com{downloadLinks[0]}";
                string portableDownloadLink = $"https://github.com{downloadLinks[1]}";
                string sourceDownloadLink = $"https://github.com{downloadLinks[^2]}";
                if (debugSetting)
                {
                    Console.WriteLine($"Latest Version: {latestVersion}");
                    Console.WriteLine($"Portable:       {portableDownloadLink}");
                    Console.WriteLine($"Installer:      {setupDownloadLink}");
                    Console.WriteLine($"Source:         {sourceDownloadLink}");
                }
                else if (File.Exists("unins000.exe"))
                {   // Was installed using the Installer
                    Download(setupDownloadLink, "MC_Installer.exe");
                    Process.Start("MC_Installer.exe", "/ VERYSILENT / CLOSEAPPLICATIONS / FORCECLOSEAPPLICATIONS / MERGETASKS = \"!desktopicon\"");
                }
                else
                {   // portable installation
                    Download(portableDownloadLink, "Portable.zip");
                    Process.Start("\"Music Caster.exe\"");
                }
            }
        }
    }
}
