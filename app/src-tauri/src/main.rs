#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[macro_use]
extern crate rust_i18n;

i18n!("locales", fallback = "en");

fn main() {
  app_lib::run();
}
