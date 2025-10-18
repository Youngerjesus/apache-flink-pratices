# Apache Flink, 스트림 처리의 정석: DataStream API 첫걸음

StreamExecutionEnvironment 객체를 통해서 스트림 처리 실행 게획이 담긴 JobGraph 를 내부적으로 만듬
- DataStream API 를 통해서 구체적으로 어떻게 처리할지 결정되겠지
그리고 execute() 를 하면 Jobmanger 에게 제출됨
- JobManager 는 TaskManager 에게 각 작업을 배분함. 워커노드와 같음. 연산자 서브태스크를 담당. 

Q) Apache Flink 에서 스트림 처리를 실행하기 전 처음으로 외부에서 데이터를 가져오는 경우 이 데이터는 DB 에 적재하고 Flink 로 보내는게 맞나? 아니면 Flink 로 바로 보내는게 맞나? 

- DB 에 적재하면 지연시간이 길어진다. 스트림 처리 어플리케이션에 올바르지 않을 수 있음. 

Q) 권장되는 패턴은 Apache Kafka 를 Flink 앞단에 두라고 함. 왜? 

- 메시지 버퍼링, 내구성 등을 위해서. 
- Flink 의 핵심은 스트림 처리 계산 엔진임. 체크포인트와 같은 기능이 있긴하지만 Kafka 와 달리 메모리 상에 데이터를 들고있는데 유실될 가능성이 있음. 
- Flink 는 체크포인트 기능으로 데이터를 특정 시점으로 복구할 수 있는데 Kafka 에서 replay 하는 걸 통해서 데이터 유실을 완전히 막고 처리를 재개할 수 있음. 
