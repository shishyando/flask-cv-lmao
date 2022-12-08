drop table if exists users;
drop table if exists cv;

create table users (
    user_id integer primary key autoincrement,
    username text not null,
    password text not null,
    name text,
    surname text
);


create table CV (
    cv_id integer primary key autoincrement,
    user_id integer not null,
    info text,
    experience text,
    skills text,
    other text,
    foreign key (user_id) references users(user_id)
);

