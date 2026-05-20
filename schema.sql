create table if not exists thoughts (
  id integer primary key,
  external_id text,
  title text,
  body text not null,
  thought_type text default 'observation',
  source text,
  project text,
  tags text,
  metadata_json text,
  created_at text not null,
  updated_at text not null
);

create unique index if not exists thoughts_external_id_idx on thoughts(external_id) where external_id is not null;
create index if not exists thoughts_created_at_idx on thoughts(created_at desc);
create index if not exists thoughts_type_idx on thoughts(thought_type);

create table if not exists chunks (
  id integer primary key,
  thought_id integer not null,
  chunk_index integer not null,
  text text not null,
  embedding_json text,
  created_at text not null,
  foreign key (thought_id) references thoughts(id) on delete cascade,
  unique (thought_id, chunk_index)
);

create index if not exists chunks_thought_id_idx on chunks(thought_id);

create table if not exists events (
  id integer primary key,
  event_type text not null,
  thought_id integer,
  details_json text,
  created_at text not null,
  foreign key (thought_id) references thoughts(id) on delete set null
);

create index if not exists events_type_created_idx on events(event_type, created_at desc);

create table if not exists sync_queue (
  id integer primary key,
  thought_id integer not null,
  target text,
  status text default 'pending',
  last_error text,
  created_at text not null,
  updated_at text not null,
  foreign key (thought_id) references thoughts(id) on delete cascade
);

create index if not exists sync_queue_status_idx on sync_queue(status, created_at);

create virtual table if not exists thoughts_fts using fts5(
  title,
  body,
  tags,
  content='thoughts',
  content_rowid='id'
);

create trigger if not exists thoughts_ai after insert on thoughts begin
  insert into thoughts_fts(rowid, title, body, tags)
  values (new.id, coalesce(new.title, ''), new.body, coalesce(new.tags, ''));
end;

create trigger if not exists thoughts_ad after delete on thoughts begin
  insert into thoughts_fts(thoughts_fts, rowid, title, body, tags)
  values ('delete', old.id, coalesce(old.title, ''), old.body, coalesce(old.tags, ''));
end;

create trigger if not exists thoughts_au after update on thoughts begin
  insert into thoughts_fts(thoughts_fts, rowid, title, body, tags)
  values ('delete', old.id, coalesce(old.title, ''), old.body, coalesce(old.tags, ''));
  insert into thoughts_fts(rowid, title, body, tags)
  values (new.id, coalesce(new.title, ''), new.body, coalesce(new.tags, ''));
end;
