use std::path::PathBuf;

use sqlx::{Connection, SqliteConnection, sqlite::SqliteConnectOptions};
use tauri_plugin_sql::{Migration, MigrationKind};

/// Reads every file metadata row and removes entries whose path no longer points to a file.
///
/// This uses its own connection so it can run as a startup background task without waiting for
/// the webview to open the database through `tauri-plugin-sql`.
pub async fn remove_invalid_file_paths(database_path: PathBuf) -> Result<u64, sqlx::Error> {
  let options = SqliteConnectOptions::new().filename(database_path);
  let mut connection = SqliteConnection::connect_with(&options).await?;
  let file_paths = sqlx::query_scalar::<_, String>("SELECT file_path FROM file_metadata")
    .fetch_all(&mut connection)
    .await?;

  let mut invalid_paths = Vec::new();
  for file_path in file_paths {
    let is_file = tokio::fs::metadata(&file_path)
      .await
      .map(|metadata| metadata.is_file())
      .unwrap_or(false);
    if !is_file {
      invalid_paths.push(file_path);
    }
  }

  if invalid_paths.is_empty() {
    return Ok(0);
  }

  let mut transaction = connection.begin().await?;
  let mut removed = 0;
  for file_path in invalid_paths {
    removed += sqlx::query("DELETE FROM file_metadata WHERE file_path = ?")
      .bind(file_path)
      .execute(&mut *transaction)
      .await?
      .rows_affected();
  }
  transaction.commit().await?;
  Ok(removed)
}

pub fn get_migrations() -> Vec<Migration> {
  vec![
    Migration {
      version: 3,
      description: "create_initial_tables",
      sql: include_str!("../migrations/0000_initial.sql"),
      kind: MigrationKind::Up,
    },
    Migration {
      version: 4,
      description: "add_genre_column",
      sql: include_str!("../migrations/0001_add_genre.sql"),
      kind: MigrationKind::Up,
    },
    Migration {
      version: 5,
      description: "add_bpm_column",
      sql: include_str!("../migrations/0002_add_bpm.sql"),
      kind: MigrationKind::Up,
    },
  ]
}
