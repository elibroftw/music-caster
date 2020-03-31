using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Net.Http;

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
                    if (entry.FullName.Contains("Updater")) continue;
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
            using (WebClient myWebClient = new WebClient())
            {
                string myStringWebResource = url;
                myWebClient.DownloadFile(myStringWebResource, outfile);
                if (outfile.EndsWith(".zip")) ExtractZip(outfile);
            }
        }

        private static List<string> DirectorySearch(string dir)
        {
            List<string> files = new List<string>();
            try
            {
                foreach (string f in Directory.GetFiles(dir))
                {
                    files.Add(Path.GetFileName(f));
                }
                foreach (string d in Directory.GetDirectories(dir))
                {
                    files.AddRange(DirectorySearch(d));
                }
            }
            catch (System.Exception ex)
            {
                Console.WriteLine(ex.Message);
            }
            return files;
        }


        static async System.Threading.Tasks.Task Main(string[] args)
        {
            HttpClient client = new HttpClient();
            Directory.SetCurrentDirectory(AppDomain.CurrentDomain.BaseDirectory);
            Dictionary<string, object> loadedSettings = new Dictionary<string, object>() { { "DEBUG", false } };

            if (File.Exists("settings.json"))
            {
                using (StreamReader r = new StreamReader("settings.json"))
                {
                    loadedSettings = JsonConvert.DeserializeObject<Dictionary<string, object>>(r.ReadToEnd());
                }
            }

            bool debugSetting = (bool)loadedSettings.GetValueOrDefault("DEBUG", false);
            string releasesURL = @"https://github.com/elibroftw/music-caster/releases";

            HtmlWeb web = new HtmlWeb();
            HtmlDocument htmlDoc = web.Load(releasesURL);
            HtmlNode releaseEntry = null;
            string latestVersion = null;
            foreach (HtmlNode node in htmlDoc.DocumentNode.SelectNodes("//div[@class='release-entry']"))
            {  // get the latest release
                string releaseType = node.SelectSingleNode(".//span/a").InnerText;
                if (releaseType == "Latest release")
                {
                    latestVersion = node.SelectSingleNode(".//a[contains(@class, 'muted-link') and contains(@class, 'css-truncate')]").GetAttributeValue("title", "0.0.0").Substring(1);
                    releaseEntry = node;
                    break;
                }
            }
            if (releaseEntry != null)
            {
                HtmlNode details = releaseEntry.SelectSingleNode(".//details[contains(@class, 'details-reset') and contains(@class, 'Details-element')]");
                List<string> downloadLinks = new List<string>();
                foreach (HtmlNode node in details.SelectNodes(".//a"))
                {  // get download links
                    string url = node.GetAttributeValue("href", "");
                    if (url != "")
                    {
                        downloadLinks.Add(url);
                    }
                }
                string setupDownloadLink = $"https://github.com{downloadLinks[0]}";
                string portableDownloadLink = $"https://github.com{downloadLinks[1]}";
                string sourceDownloadLink = $"https://github.com{downloadLinks[downloadLinks.Count - 2]}";
                if (debugSetting)
                {
                    Console.WriteLine($"Latest Version: {latestVersion}");
                    Console.WriteLine($"Portable: {portableDownloadLink}");
                    Console.WriteLine($"Installer: {setupDownloadLink}");
                    Console.WriteLine($"Source: {sourceDownloadLink}");
                }
                else if (File.Exists("unins000.exe"))
                {
                    Download(setupDownloadLink, "MC_Installer.exe");
                    Process.Start("MC_Installer.exe / VERYSILENT / CLOSEAPPLICATIONS / FORCECLOSEAPPLICATIONS / MERGETASKS = \"!desktopicon\"");
                }
                else  // portable installation
                {
                    Download(portableDownloadLink, "Portable.zip");
                    Process.Start("\"Music Caster.exe\"");
                }
            }
        }
    }
}
