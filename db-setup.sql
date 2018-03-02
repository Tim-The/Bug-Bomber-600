-- Creating the table for the permssions system
CREATE TABLE IF NOT EXISTS permissions(role_id VARCHAR(25) NOT NULL,permission TEXT NOT NULL,ID INT PRIMARY KEY NOT NULL AUTO_INCREMENT) ENGINE = InnoDB;
CREATE TABLE IF NOT EXISTS hugs(ID INT PRIMARY KEY NOT NULL AUTO_INCREMENT, hug TEXT NOT NULL, author BIGINT);
CREATE TABLE IF NOT EXISTS fights(ID INT PRIMARY KEY NOT NULL AUTO_INCREMENT, fight TEXT NOT NULL, author BIGINT);
CREATE TABLE IF NOT EXISTS events(ID INT PRIMARY KEY NOT NULL AUTO_INCREMENT, name VARCHAR(100) NOT NULL UNIQUE, started BOOLEAN NOT NULL DEFAULT 0, ended BOOLEAN NOT NULL DEFAULT 0, endtime BIGINT, duration BIGINT, closingTime BIGINT, leaderboard BIGINT NULL);
CREATE TABLE IF NOT EXISTS eventChannels(channel BIGINT NOT NULL,event INT,type INT NOT NULL, name VARCHAR(20) NOT NULL, CONSTRAINT eventChannels_channel_event_pk PRIMARY KEY (channel, event), CONSTRAINT table_name_events_ID_fk FOREIGN KEY (event) REFERENCES events (ID));
CREATE TABLE IF NOT EXISTS submissions(ID INT PRIMARY KEY NOT NULL AUTO_INCREMENT,event INT NOT NULL,user BIGINT NOT NULL,submission TEXT NOT NULL,points INT DEFAULT 0 NOT NULL,CONSTRAINT submissions_events_ID_fk FOREIGN KEY (event) REFERENCES events (ID));