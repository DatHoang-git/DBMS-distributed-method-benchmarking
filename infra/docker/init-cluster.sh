#!/usr/bin/env bash
# Initialize Phase 0 local MongoDB 7.0 sharded cluster (chunkSize=32MB, 2 shards)
set -euo pipefail

echo "Waiting for mongod containers..."
sleep 4

docker exec mdb-cfgsvr mongosh --port 27019 --eval 'rs.initiate({_id:"cfgRS", configsvr:true, members:[{_id:0, host:"cfgsvr:27019"}]})'
docker exec mdb-shard1 mongosh --port 27018 --eval 'rs.initiate({_id:"shard1RS", members:[{_id:0, host:"shard1:27018"}]})'
docker exec mdb-shard2 mongosh --port 27018 --eval 'rs.initiate({_id:"shard2RS", members:[{_id:0, host:"shard2:27018"}]})'

echo "Waiting for RS primaries..."
sleep 6

docker exec mdb-mongos mongosh --port 27017 --eval '
  sh.addShard("shard1RS/shard1:27018");
  sh.addShard("shard2RS/shard2:27018");
  db.getSiblingDB("config").settings.updateOne(
    {_id: "chunksize"}, {$set: {value: 32}}, {upsert: true}
  );
  sh.enableSharding("ehr");
  sh.shardCollection("ehr.patients", {_id: "hashed"});
  sh.shardCollection("ehr.encounters", {PATIENT: "hashed"}, false, {numInitialChunks: 16});
  const col = db.getSiblingDB("ehr").encounters;
  col.createIndex({PATIENT: 1, START: -1});
  col.createIndex({START: 1});
  col.createIndex({"conditions.CODE": 1, START: 1});
  sh.stopBalancer();
  printjson(db.adminCommand("balancerStatus"));
  sh.status();
'
echo "Phase 0 cluster ready on mongodb://localhost:27017"
