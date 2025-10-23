use tauri_plugin_sql::{Migration, MigrationKind};

pub fn get_migrations() -> Vec<Migration> {
  vec![Migration {
    version: 3,
    description: "create_initial_tables",
    sql: include_str!("../migrations/0000_initial.sql"),
    kind: MigrationKind::Up,
  }]
}
