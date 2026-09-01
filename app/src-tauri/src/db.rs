use tauri_plugin_sql::{Migration, MigrationKind};

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
