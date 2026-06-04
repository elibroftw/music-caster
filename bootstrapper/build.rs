use std::path::PathBuf;

const ICO_PREFERRED_SIZE: u32 = 48;

fn main() {
    println!("cargo:rerun-if-changed=icon.ico");

    if std::env::var_os("CARGO_CFG_WINDOWS").is_some() {
        let mut res = winresource::WindowsResource::new();
        res.set_icon("icon.ico");
        if let Err(e) = res.compile() {
            println!("cargo:warning=failed to embed icon: {e}");
        }
    }

    bake_window_icon();
}

fn bake_window_icon() {
    let out_dir = PathBuf::from(std::env::var("OUT_DIR").expect("OUT_DIR set by cargo"));

    let (rgba, size) = decode_frame().unwrap_or_else(|e| {
        println!("cargo:warning=failed to decode window icon: {e}");
        (Vec::new(), 0)
    });

    std::fs::write(out_dir.join("window_icon.bin"), &rgba).expect("write window_icon.bin");
    std::fs::write(
        out_dir.join("window_icon.rs"),
        format!(
            "pub static ICON_RGBA: &[u8] = include_bytes!(\"window_icon.bin\");\n\
             pub const ICON_SIZE: u32 = {size};\n"
        ),
    )
    .expect("write window_icon.rs");
}

fn decode_frame() -> Result<(Vec<u8>, u32), String> {
    let file = std::fs::File::open("icon.ico").map_err(|e| format!("open icon.ico: {e}"))?;
    let dir = ico::IconDir::read(file).map_err(|e| format!("parse icon.ico: {e}"))?;

    let entry = dir
        .entries()
        .iter()
        .min_by_key(|e| e.width().abs_diff(ICO_PREFERRED_SIZE))
        .ok_or("icon.ico has no frames")?;

    let image = entry.decode().map_err(|e| format!("decode frame: {e}"))?;
    Ok((image.rgba_data().to_vec(), image.width()))
}
