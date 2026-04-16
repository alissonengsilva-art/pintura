-- MySQL dump 10.13  Distrib 8.0.43, for Win64 (x86_64)
--
-- Host: localhost    Database: pintura
-- ------------------------------------------------------
-- Server version	8.0.43

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `alembic_version`
--

DROP TABLE IF EXISTS `alembic_version`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `alembic_version`
--

LOCK TABLES `alembic_version` WRITE;
/*!40000 ALTER TABLE `alembic_version` DISABLE KEYS */;
INSERT INTO `alembic_version` VALUES ('20260416_0010');
/*!40000 ALTER TABLE `alembic_version` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `aspecto_lancamentos`
--

DROP TABLE IF EXISTS `aspecto_lancamentos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `aspecto_lancamentos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `data_referencia` date NOT NULL,
  `turno` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `modelo` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `responsavel_nome` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `total_registros` int NOT NULL DEFAULT '0',
  `total_quantidade` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_aspecto_lancamentos_data_referencia` (`data_referencia`),
  KEY `ix_aspecto_lancamentos_turno` (`turno`),
  KEY `ix_aspecto_lancamentos_modelo` (`modelo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `aspecto_lancamentos`
--

LOCK TABLES `aspecto_lancamentos` WRITE;
/*!40000 ALTER TABLE `aspecto_lancamentos` DISABLE KEYS */;
/*!40000 ALTER TABLE `aspecto_lancamentos` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `aspecto_registros`
--

DROP TABLE IF EXISTS `aspecto_registros`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `aspecto_registros` (
  `id` int NOT NULL AUTO_INCREMENT,
  `lancamento_id` int NOT NULL,
  `data_referencia` date NOT NULL,
  `turno` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `modelo` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `responsavel_nome` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `cis` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `cod_posicao` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `local` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `anomalia` varchar(160) COLLATE utf8mb4_unicode_ci NOT NULL,
  `lado` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `geracao` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `quantidade` int NOT NULL DEFAULT '1',
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_aspecto_registros_lancamento_id` (`lancamento_id`),
  KEY `ix_aspecto_registros_data_referencia` (`data_referencia`),
  KEY `ix_aspecto_registros_turno` (`turno`),
  KEY `ix_aspecto_registros_modelo` (`modelo`),
  KEY `ix_aspecto_registros_cis` (`cis`),
  KEY `ix_aspecto_registros_anomalia` (`anomalia`),
  CONSTRAINT `aspecto_registros_ibfk_1` FOREIGN KEY (`lancamento_id`) REFERENCES `aspecto_lancamentos` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `aspecto_registros`
--

LOCK TABLES `aspecto_registros` WRITE;
/*!40000 ALTER TABLE `aspecto_registros` DISABLE KEYS */;
/*!40000 ALTER TABLE `aspecto_registros` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `ed_lancamento_itens`
--

DROP TABLE IF EXISTS `ed_lancamento_itens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ed_lancamento_itens` (
  `id` int NOT NULL AUTO_INCREMENT,
  `lancamento_id` int NOT NULL,
  `item_ed_id` int NOT NULL,
  `valor_informado` varchar(150) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `observacao_item` text COLLATE utf8mb4_unicode_ci,
  `fora_parametro` tinyint(1) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_ed_lancamento_itens_lancamento_id` (`lancamento_id`),
  KEY `ix_ed_lancamento_itens_item_ed_id` (`item_ed_id`),
  CONSTRAINT `ed_lancamento_itens_ibfk_1` FOREIGN KEY (`lancamento_id`) REFERENCES `ed_lancamentos` (`id`) ON DELETE CASCADE,
  CONSTRAINT `ed_lancamento_itens_ibfk_2` FOREIGN KEY (`item_ed_id`) REFERENCES `itens_ed` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ed_lancamento_itens`
--

LOCK TABLES `ed_lancamento_itens` WRITE;
/*!40000 ALTER TABLE `ed_lancamento_itens` DISABLE KEYS */;
INSERT INTO `ed_lancamento_itens` VALUES (1,3,1,'22',NULL,0,'2026-04-13 11:22:35','2026-04-13 11:22:35'),(2,3,2,'2',NULL,0,'2026-04-13 11:22:35','2026-04-13 11:22:35'),(3,3,3,'11',NULL,0,'2026-04-13 11:22:35','2026-04-13 11:22:35'),(4,3,4,'6',NULL,0,'2026-04-13 11:22:35','2026-04-13 11:22:35'),(5,3,5,'1322',NULL,0,'2026-04-13 11:22:35','2026-04-13 11:22:35'),(6,3,18,'2',NULL,0,'2026-04-13 11:22:35','2026-04-13 11:22:35'),(7,3,19,'522',NULL,0,'2026-04-13 11:22:35','2026-04-13 11:22:35'),(8,3,22,'5',NULL,0,'2026-04-13 11:22:35','2026-04-13 11:22:35'),(9,3,23,'500',NULL,0,'2026-04-13 11:22:35','2026-04-13 11:22:35'),(10,3,24,'1',NULL,0,'2026-04-13 11:22:35','2026-04-13 11:22:35'),(11,3,25,'5',NULL,0,'2026-04-13 11:22:35','2026-04-13 11:22:35'),(12,3,26,'666',NULL,0,'2026-04-13 11:22:35','2026-04-13 11:22:35'),(13,3,27,'1',NULL,0,'2026-04-13 11:22:35','2026-04-13 11:22:35'),(14,3,28,'5',NULL,0,'2026-04-13 11:22:35','2026-04-13 11:22:35'),(15,3,29,'555',NULL,0,'2026-04-13 11:22:35','2026-04-13 11:22:35'),(16,3,30,'1',NULL,0,'2026-04-13 11:22:35','2026-04-13 11:22:35'),(17,3,32,'9',NULL,NULL,'2026-04-13 11:22:35','2026-04-13 11:22:35'),(18,3,35,'11',NULL,0,'2026-04-13 11:22:35','2026-04-13 11:22:35');
/*!40000 ALTER TABLE `ed_lancamento_itens` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `ed_lancamentos`
--

DROP TABLE IF EXISTS `ed_lancamentos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ed_lancamentos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `data_referencia` date NOT NULL,
  `tipo_dia` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `setor` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `turno` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `responsavel_nome` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'rascunho',
  `observacoes_gerais` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_ed_lancamentos_data_referencia` (`data_referencia`),
  KEY `ix_ed_lancamentos_status` (`status`),
  KEY `ix_ed_lancamentos_setor_turno` (`setor`,`turno`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ed_lancamentos`
--

LOCK TABLES `ed_lancamentos` WRITE;
/*!40000 ALTER TABLE `ed_lancamentos` DISABLE KEYS */;
INSERT INTO `ed_lancamentos` VALUES (3,'2026-04-13','normal','Laboratório','1','Gesiane Monteiro','concluido',NULL,'2026-04-13 11:22:35','2026-04-13 13:39:34');
/*!40000 ALTER TABLE `ed_lancamentos` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `espessura_ed_itens`
--

DROP TABLE IF EXISTS `espessura_ed_itens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `espessura_ed_itens` (
  `id` int NOT NULL AUTO_INCREMENT,
  `lancamento_id` int NOT NULL,
  `ponto_numero` int NOT NULL,
  `valor_espessura` float DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_espessura_ed_lancamento_ponto` (`lancamento_id`,`ponto_numero`),
  KEY `ix_espessura_ed_itens_lancamento_id` (`lancamento_id`),
  KEY `ix_espessura_ed_itens_ponto_numero` (`ponto_numero`),
  CONSTRAINT `espessura_ed_itens_ibfk_1` FOREIGN KEY (`lancamento_id`) REFERENCES `espessura_ed_lancamentos` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `espessura_ed_itens`
--

LOCK TABLES `espessura_ed_itens` WRITE;
/*!40000 ALTER TABLE `espessura_ed_itens` DISABLE KEYS */;
/*!40000 ALTER TABLE `espessura_ed_itens` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `espessura_ed_lancamentos`
--

DROP TABLE IF EXISTS `espessura_ed_lancamentos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `espessura_ed_lancamentos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `data_referencia` date NOT NULL,
  `turno` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `modelo` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `responsavel_nome` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `cis` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'rascunho',
  `observacoes_gerais` text COLLATE utf8mb4_unicode_ci,
  `total_pontos_preenchidos` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_espessura_ed_lancamentos_data_referencia` (`data_referencia`),
  KEY `ix_espessura_ed_lancamentos_turno` (`turno`),
  KEY `ix_espessura_ed_lancamentos_modelo` (`modelo`),
  KEY `ix_espessura_ed_lancamentos_status` (`status`),
  KEY `ix_espessura_ed_lancamentos_cis` (`cis`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `espessura_ed_lancamentos`
--

LOCK TABLES `espessura_ed_lancamentos` WRITE;
/*!40000 ALTER TABLE `espessura_ed_lancamentos` DISABLE KEYS */;
/*!40000 ALTER TABLE `espessura_ed_lancamentos` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `itens_ed`
--

DROP TABLE IF EXISTS `itens_ed`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `itens_ed` (
  `id` int NOT NULL AUTO_INCREMENT,
  `operacao_equipamento` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `descricao_controle` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `norma` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `parametro` varchar(150) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `frequencia` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `responsavel_padrao` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `setor_padrao` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `turno_padrao` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `numero_coleta` int DEFAULT NULL,
  `ativo` tinyint(1) NOT NULL DEFAULT '1',
  `ordem_exibicao` int NOT NULL DEFAULT '0',
  `observacao` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=40 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `itens_ed`
--

LOCK TABLES `itens_ed` WRITE;
/*!40000 ALTER TABLE `itens_ed` DISABLE KEYS */;
INSERT INTO `itens_ed` VALUES (1,'BANHO DE TINTA','RESIDUO SECO (NVC)','SGU JPM16','22 - 26 %','1XDIA','Laboratório','Laboratório','1XDIA',1,1,1,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(2,'BANHO DE TINTA','CINZAS','SGU JPM08','1,9 - 3,4%','1XDIA','Laboratório','Laboratório','1XDIA',1,1,2,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(3,'BANHO DE TINTA','RELACAO P/B','SGU JPM19','10,0 - 16,0','1XDIA','Laboratório','Laboratório','1XDIA',1,1,3,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(4,'BANHO DE TINTA','PH','SGU JPM06','5,3 - 6,3','1XDIA','Laboratório','Laboratório','1XDIA',1,1,4,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(5,'BANHO DE TINTA','CONDUTIVIDADE','SGU JPM09','1300 - 2400 mS','1XDIA','Laboratório','Laboratório','1XDIA',1,1,5,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(6,'BANHO DE TINTA','TEMPERATURA DO BANHO',NULL,'<35ºC','2XTURNO','Condutor PT/ED','PT/ED','1',1,1,6,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(7,'BANHO DE TINTA','TEMPERATURA DO BANHO',NULL,'<35ºC','2XTURNO','Condutor PT/ED','PT/ED','1',2,1,7,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(8,'BANHO DE TINTA','TEMPERATURA DO BANHO',NULL,'<35ºC','2XTURNO','Condutor PT/ED','PT/ED','2',1,1,8,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(9,'BANHO DE TINTA','TEMPERATURA DO BANHO',NULL,'<35ºC','2XTURNO','Condutor PT/ED','PT/ED','2',2,1,9,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(10,'BANHO DE TINTA','TEMPERATURA DO BANHO',NULL,'<35ºC','2XTURNO','Condutor PT/ED','PT/ED','3',1,1,10,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(11,'BANHO DE TINTA','TEMPERATURA DO BANHO',NULL,'<35ºC','2XTURNO','Condutor PT/ED','PT/ED','3',2,1,11,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(12,'BANHO DE TINTA','TENSÃO DOS RETIFICADORES',NULL,'80 - 400V','1XTURNO','Condutor PT/ED','PT/ED','1',1,1,12,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(13,'BANHO DE TINTA','TENSÃO DOS RETIFICADORES',NULL,'80 - 400V','1XTURNO','Condutor PT/ED','PT/ED','2',1,1,13,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(14,'BANHO DE TINTA','TENSÃO DOS RETIFICADORES',NULL,'80 - 400V','1XTURNO','Condutor PT/ED','PT/ED','3',1,1,14,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(15,'BANHO DE TINTA','PRESSÃO NOS FILTROS',NULL,'DP<=1','1XTURNO','Condutor PT/ED','PT/ED','1',1,1,15,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(16,'BANHO DE TINTA','PRESSÃO NOS FILTROS',NULL,'DP<=1','1XTURNO','Condutor PT/ED','PT/ED','2',1,1,16,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(17,'BANHO DE TINTA','PRESSÃO NOS FILTROS',NULL,'DP<=1','1XTURNO','Condutor PT/ED','PT/ED','3',1,1,17,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(18,'ANOLITO','pH','SGU JPM06','1,5 - 3,5','1XDIA','Laboratório','Laboratório','1XDIA',1,1,18,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(19,'ANOLITO','CONDUTIVIDADE','SGU JPM09','500 - 5000 mS','1XDIA','Laboratório','Laboratório','1XDIA',1,1,19,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(20,'ANOLITO','VAZÃO CELULAS DIÁLISE','SGU JPM24','≥2,5 L/min (≥ 150 L/h)','1X2SEMANAS','Condutor PT/ED','PT/ED','1X2SEMANAS',1,1,20,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(21,'ANOLITO','CONSUMO DE CORRENTE CELULAS DIALISE',NULL,'<200 A','1XMES','Condutor PT/ED','PT/ED','1XMES',1,1,21,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(22,'UF1','pH','SGU JPM06','5,0 - 6,0','1XDIA','Laboratório','Laboratório','1XDIA',1,1,22,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(23,'UF1','CONDUTIVIDADE','SGU JPM09','500 - 1200 mS','1XDIA','Laboratório','Laboratório','1XDIA',1,1,23,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(24,'UF1','RESIDUO SECO (NVC)','SGU JPM16','<1,5%','1XDIA','Laboratório','Laboratório','1XDIA',1,1,24,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(25,'UF2','pH','SGU JPM06','5,0 - 6,0','1XDIA','Laboratório','Laboratório','1XDIA',1,1,25,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(26,'UF2','CONDUTIVIDADE','SGU JPM09','500 - 1200 mS','1XDIA','Laboratório','Laboratório','1XDIA',1,1,26,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(27,'UF2','RESIDUO SECO (NVC)','SGU JPM16','<1,5%','1XDIA','Laboratório','Laboratório','1XDIA',1,1,27,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(28,'UF3','pH','SGU JPM06','5,0 - 6,0','1XDIA','Laboratório','Laboratório','1XDIA',1,1,28,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(29,'UF3','CONDUTIVIDADE','SGU JPM09','500 - 1200 mS','1XDIA','Laboratório','Laboratório','1XDIA',1,1,29,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(30,'UF3','RESIDUO SECO (NVC)','SGU JPM16','<1,5%','1XDIA','Laboratório','Laboratório','1XDIA',1,1,30,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(31,'UF1, 2 e 3','VAZÃO','SGU JPM24','≥ 400 x 0,8 l/h (≥ 3,2 m³/h)','1XDIA','Condutor PT/ED','PT/ED','1XDIA',1,1,31,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(32,'ÁGUA DEMI','CONDUTIVIDADE','SGU JPM09','≤10µS','1XDIA','Laboratório','Laboratório','1XDIA',1,1,32,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(33,'FORNO ED','TEMPERATURA INTERNA',NULL,'<220ºC','2XSEMANA','Condutor PT/ED','PT/ED','2XSEMANA',1,1,33,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(34,'FORNO ED','CURVA DE COZIMENTO (DATAPAQ)',NULL,'>20min a 160ºC','1XSEMANA','Condutor PT/ED','PT/ED','1XSEMANA',1,1,34,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(35,'CARACTERISTICA FILME DE CATAFORESE','RUGOSIDADE CAPO E PORTAS (PPG)','3 CARROS POR MODELO (ALTERNANDO OS MODELOS)','<=14u inch','1XDIA','Fornecedor/Laboratório','Fornecedor','1XDIA',1,1,35,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(36,'CARACTERISTICA FILME DE CATAFORESE','COLATURA E GOTA - APARENCIA EXTERNA','3 CARROS POR MODELO (ALTERNANDO OS MODELOS)','Menor melhor','1XTURNO','Condutor PT/ED','PT/ED','1',1,1,36,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(37,'CARACTERISTICA FILME DE CATAFORESE','COLATURA E GOTA - APARENCIA EXTERNA','3 CARROS POR MODELO (ALTERNANDO OS MODELOS)','Menor melhor','1XTURNO','Condutor PT/ED','PT/ED','2',1,1,37,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(38,'CARACTERISTICA FILME DE CATAFORESE','COLATURA E GOTA - APARENCIA EXTERNA','3 CARROS POR MODELO (ALTERNANDO OS MODELOS)','Menor melhor','1XTURNO','Condutor PT/ED','PT/ED','3',1,1,38,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(39,'CARACTERISTICA FILME DE CATAFORESE','ESPESSURA',NULL,NULL,NULL,'Condutor PT/ED','PT/ED','1',1,1,39,NULL,'2026-04-13 09:54:34','2026-04-13 09:54:34');
/*!40000 ALTER TABLE `itens_ed` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `modelos`
--

DROP TABLE IF EXISTS `modelos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `modelos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nome` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `codigo` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ativo` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `nome` (`nome`),
  UNIQUE KEY `codigo` (`codigo`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `modelos`
--

LOCK TABLES `modelos` WRITE;
/*!40000 ALTER TABLE `modelos` DISABLE KEYS */;
INSERT INTO `modelos` VALUES (2,'RANEGADE','521',1,'2026-04-13 14:51:04','2026-04-13 14:51:04'),(3,'COMMANDER','598',1,'2026-04-13 14:51:36','2026-04-13 14:51:36'),(4,'TORO','226',1,'2026-04-13 14:51:55','2026-04-13 14:51:55'),(5,'COMPASS','551',1,'2026-04-13 14:52:06','2026-04-13 14:52:06'),(6,'RAMPAGE','291',1,'2026-04-13 14:52:19','2026-04-13 14:52:19');
/*!40000 ALTER TABLE `modelos` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `operational_module_records`
--

DROP TABLE IF EXISTS `operational_module_records`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `operational_module_records` (
  `id` int NOT NULL AUTO_INCREMENT,
  `module_code` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `data_referencia` date NOT NULL,
  `turno` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `context_key` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status_geral` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `context_data` json NOT NULL,
  `legacy_count` int NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_operational_module_context` (`module_code`,`context_key`),
  KEY `ix_operational_module_records_module_code` (`module_code`),
  KEY `ix_operational_module_records_data_referencia` (`data_referencia`),
  KEY `ix_operational_module_records_turno` (`turno`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `operational_module_records`
--

LOCK TABLES `operational_module_records` WRITE;
/*!40000 ALTER TABLE `operational_module_records` DISABLE KEYS */;
INSERT INTO `operational_module_records` VALUES (1,'temperatura-forno-ed','2026-04-16',NULL,'temperatura-forno-ed|data_referencia=2026-04-16','EM_ANDAMENTO','{\"data_referencia\": \"2026-04-16\"}',0,'2026-04-16 18:06:05','2026-04-16 18:08:51');
/*!40000 ALTER TABLE `operational_module_records` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `operational_module_sector_entries`
--

DROP TABLE IF EXISTS `operational_module_sector_entries`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `operational_module_sector_entries` (
  `id` int NOT NULL AUTO_INCREMENT,
  `setor_registro_id` int NOT NULL,
  `referencia` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ordem` int NOT NULL,
  `valor_texto` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `valor_numero` float DEFAULT NULL,
  `observacao` text COLLATE utf8mb4_unicode_ci,
  `fora_padrao` tinyint(1) DEFAULT NULL,
  `dados` json NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_operational_module_sector_entries_setor_registro_id` (`setor_registro_id`),
  CONSTRAINT `operational_module_sector_entries_ibfk_1` FOREIGN KEY (`setor_registro_id`) REFERENCES `operational_module_sector_records` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=25 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `operational_module_sector_entries`
--

LOCK TABLES `operational_module_sector_entries` WRITE;
/*!40000 ALTER TABLE `operational_module_sector_entries` DISABLE KEYS */;
INSERT INTO `operational_module_sector_entries` VALUES (13,1,'1',1,'12',12,NULL,1,'{\"flag\": true, \"label\": \"Zona 1\", \"order\": 1, \"value\": \"12\", \"expected\": \"60 a 120 °C\", \"faixa_max\": 120.0, \"faixa_min\": 60.0, \"reference\": \"1\", \"status_label\": \"Fora do padrão\", \"value_number\": 12.0}','2026-04-16 18:08:51','2026-04-16 18:08:51'),(14,1,'2',2,'12',12,NULL,1,'{\"flag\": true, \"label\": \"Zona 2\", \"order\": 2, \"value\": \"12\", \"expected\": \"60 a 120 °C\", \"faixa_max\": 120.0, \"faixa_min\": 60.0, \"reference\": \"2\", \"status_label\": \"Fora do padrão\", \"value_number\": 12.0}','2026-04-16 18:08:51','2026-04-16 18:08:51'),(15,1,'3',3,'',NULL,NULL,0,'{\"flag\": false, \"label\": \"Zona 3\", \"order\": 3, \"value\": \"\", \"expected\": \"100 a 160 °C\", \"faixa_max\": 160.0, \"faixa_min\": 100.0, \"reference\": \"3\", \"status_label\": \"Não avaliado\", \"value_number\": null}','2026-04-16 18:08:51','2026-04-16 18:08:51'),(16,1,'4',4,'',NULL,NULL,0,'{\"flag\": false, \"label\": \"Zona 4\", \"order\": 4, \"value\": \"\", \"expected\": \"150 a 190 °C\", \"faixa_max\": 190.0, \"faixa_min\": 150.0, \"reference\": \"4\", \"status_label\": \"Não avaliado\", \"value_number\": null}','2026-04-16 18:08:51','2026-04-16 18:08:51'),(17,1,'5',5,'',NULL,NULL,0,'{\"flag\": false, \"label\": \"Zona 5\", \"order\": 5, \"value\": \"\", \"expected\": \"140 a 180 °C\", \"faixa_max\": 180.0, \"faixa_min\": 140.0, \"reference\": \"5\", \"status_label\": \"Não avaliado\", \"value_number\": null}','2026-04-16 18:08:51','2026-04-16 18:08:51'),(18,1,'6',6,'',NULL,NULL,0,'{\"flag\": false, \"label\": \"Zona 6\", \"order\": 6, \"value\": \"\", \"expected\": \"160 a 200 °C\", \"faixa_max\": 200.0, \"faixa_min\": 160.0, \"reference\": \"6\", \"status_label\": \"Não avaliado\", \"value_number\": null}','2026-04-16 18:08:51','2026-04-16 18:08:51'),(19,1,'7',7,'',NULL,NULL,0,'{\"flag\": false, \"label\": \"Zona 7\", \"order\": 7, \"value\": \"\", \"expected\": \"160 a 200 °C\", \"faixa_max\": 200.0, \"faixa_min\": 160.0, \"reference\": \"7\", \"status_label\": \"Não avaliado\", \"value_number\": null}','2026-04-16 18:08:51','2026-04-16 18:08:51'),(20,1,'8',8,'',NULL,NULL,0,'{\"flag\": false, \"label\": \"Zona 8\", \"order\": 8, \"value\": \"\", \"expected\": \"160 a 200 °C\", \"faixa_max\": 200.0, \"faixa_min\": 160.0, \"reference\": \"8\", \"status_label\": \"Não avaliado\", \"value_number\": null}','2026-04-16 18:08:51','2026-04-16 18:08:51'),(21,1,'9',9,'',NULL,NULL,0,'{\"flag\": false, \"label\": \"Zona 9\", \"order\": 9, \"value\": \"\", \"expected\": \"160 a 200 °C\", \"faixa_max\": 200.0, \"faixa_min\": 160.0, \"reference\": \"9\", \"status_label\": \"Não avaliado\", \"value_number\": null}','2026-04-16 18:08:51','2026-04-16 18:08:51'),(22,1,'10',10,'',NULL,NULL,0,'{\"flag\": false, \"label\": \"Zona 10\", \"order\": 10, \"value\": \"\", \"expected\": \"160 a 200 °C\", \"faixa_max\": 200.0, \"faixa_min\": 160.0, \"reference\": \"10\", \"status_label\": \"Não avaliado\", \"value_number\": null}','2026-04-16 18:08:51','2026-04-16 18:08:51'),(23,1,'11',11,'',NULL,NULL,0,'{\"flag\": false, \"label\": \"Zona 11\", \"order\": 11, \"value\": \"\", \"expected\": \"160 a 200 °C\", \"faixa_max\": 200.0, \"faixa_min\": 160.0, \"reference\": \"11\", \"status_label\": \"Não avaliado\", \"value_number\": null}','2026-04-16 18:08:51','2026-04-16 18:08:51'),(24,1,'12',12,'',NULL,NULL,0,'{\"flag\": false, \"label\": \"Zona 12\", \"order\": 12, \"value\": \"\", \"expected\": \"160 a 200 °C\", \"faixa_max\": 200.0, \"faixa_min\": 160.0, \"reference\": \"12\", \"status_label\": \"Não avaliado\", \"value_number\": null}','2026-04-16 18:08:51','2026-04-16 18:08:51');
/*!40000 ALTER TABLE `operational_module_sector_entries` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `operational_module_sector_records`
--

DROP TABLE IF EXISTS `operational_module_sector_records`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `operational_module_sector_records` (
  `id` int NOT NULL AUTO_INCREMENT,
  `registro_mestre_id` int NOT NULL,
  `setor_tipo` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `responsavel_nome` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `observacoes_setor` text COLLATE utf8mb4_unicode_ci,
  `status_setor` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `metricas` json NOT NULL,
  `iniciado_em` datetime DEFAULT NULL,
  `atualizado_em` datetime DEFAULT NULL,
  `concluido_em` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_operational_module_sector` (`registro_mestre_id`,`setor_tipo`),
  KEY `ix_operational_module_sector_records_registro_mestre_id` (`registro_mestre_id`),
  CONSTRAINT `operational_module_sector_records_ibfk_1` FOREIGN KEY (`registro_mestre_id`) REFERENCES `operational_module_records` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `operational_module_sector_records`
--

LOCK TABLES `operational_module_sector_records` WRITE;
/*!40000 ALTER TABLE `operational_module_sector_records` DISABLE KEYS */;
INSERT INTO `operational_module_sector_records` VALUES (1,1,'PTED','ALISSON JORGE',NULL,'EM_ANDAMENTO','{\"total\": 12, \"flag_count\": 2, \"percentual\": 17, \"preenchidos\": 2}','2026-04-16 18:06:05','2026-04-16 18:08:51',NULL),(2,1,'LABORATORIO',NULL,NULL,'NAO_INICIADO','{}',NULL,NULL,NULL);
/*!40000 ALTER TABLE `operational_module_sector_records` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `poder_penetracao_itens`
--

DROP TABLE IF EXISTS `poder_penetracao_itens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `poder_penetracao_itens` (
  `id` int NOT NULL AUTO_INCREMENT,
  `lancamento_id` int NOT NULL,
  `ponto_numero` int NOT NULL,
  `valor_medido` float DEFAULT NULL,
  `aprovado` tinyint(1) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_poder_penetracao_lancamento_ponto` (`lancamento_id`,`ponto_numero`),
  KEY `ix_poder_penetracao_itens_lancamento_id` (`lancamento_id`),
  KEY `ix_poder_penetracao_itens_ponto_numero` (`ponto_numero`),
  CONSTRAINT `poder_penetracao_itens_ibfk_1` FOREIGN KEY (`lancamento_id`) REFERENCES `poder_penetracao_lancamentos` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `poder_penetracao_itens`
--

LOCK TABLES `poder_penetracao_itens` WRITE;
/*!40000 ALTER TABLE `poder_penetracao_itens` DISABLE KEYS */;
/*!40000 ALTER TABLE `poder_penetracao_itens` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `poder_penetracao_lancamentos`
--

DROP TABLE IF EXISTS `poder_penetracao_lancamentos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `poder_penetracao_lancamentos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `data_referencia` date NOT NULL,
  `semana_referencia` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `modelo` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `responsavel_nome` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `cis` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `velocidade` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tipo` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `menor_valor` float DEFAULT NULL,
  `total_pontos` int NOT NULL DEFAULT '0',
  `total_aprovados` int NOT NULL DEFAULT '0',
  `total_reprovados` int NOT NULL DEFAULT '0',
  `percentual_aprovacao` float NOT NULL DEFAULT '0',
  `observacoes` text COLLATE utf8mb4_unicode_ci,
  `acao_corretiva` text COLLATE utf8mb4_unicode_ci,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'rascunho',
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_poder_penetracao_lancamentos_data_referencia` (`data_referencia`),
  KEY `ix_poder_penetracao_lancamentos_semana_referencia` (`semana_referencia`),
  KEY `ix_poder_penetracao_lancamentos_modelo` (`modelo`),
  KEY `ix_poder_penetracao_lancamentos_status` (`status`),
  KEY `ix_poder_penetracao_lancamentos_cis` (`cis`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `poder_penetracao_lancamentos`
--

LOCK TABLES `poder_penetracao_lancamentos` WRITE;
/*!40000 ALTER TABLE `poder_penetracao_lancamentos` DISABLE KEYS */;
/*!40000 ALTER TABLE `poder_penetracao_lancamentos` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `pressao_filtros_itens`
--

DROP TABLE IF EXISTS `pressao_filtros_itens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pressao_filtros_itens` (
  `id` int NOT NULL AUTO_INCREMENT,
  `lancamento_id` int NOT NULL,
  `filtro_numero` int NOT NULL,
  `valor_pressao` float DEFAULT NULL,
  `em_alarme` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_pressao_filtros_lancamento_filtro` (`lancamento_id`,`filtro_numero`),
  KEY `ix_pressao_filtros_itens_lancamento_id` (`lancamento_id`),
  KEY `ix_pressao_filtros_itens_filtro_numero` (`filtro_numero`),
  CONSTRAINT `pressao_filtros_itens_ibfk_1` FOREIGN KEY (`lancamento_id`) REFERENCES `pressao_filtros_lancamentos` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `pressao_filtros_itens`
--

LOCK TABLES `pressao_filtros_itens` WRITE;
/*!40000 ALTER TABLE `pressao_filtros_itens` DISABLE KEYS */;
/*!40000 ALTER TABLE `pressao_filtros_itens` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `pressao_filtros_lancamentos`
--

DROP TABLE IF EXISTS `pressao_filtros_lancamentos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pressao_filtros_lancamentos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `data_referencia` date NOT NULL,
  `turno` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `responsavel_nome` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'rascunho',
  `observacoes_gerais` text COLLATE utf8mb4_unicode_ci,
  `total_filtros_em_alarme` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_pressao_filtros_lancamentos_data_referencia` (`data_referencia`),
  KEY `ix_pressao_filtros_lancamentos_turno` (`turno`),
  KEY `ix_pressao_filtros_lancamentos_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `pressao_filtros_lancamentos`
--

LOCK TABLES `pressao_filtros_lancamentos` WRITE;
/*!40000 ALTER TABLE `pressao_filtros_lancamentos` DISABLE KEYS */;
/*!40000 ALTER TABLE `pressao_filtros_lancamentos` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `responsaveis`
--

DROP TABLE IF EXISTS `responsaveis`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `responsaveis` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nome` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `descricao` text COLLATE utf8mb4_unicode_ci,
  `ativo` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `nome` (`nome`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `responsaveis`
--

LOCK TABLES `responsaveis` WRITE;
/*!40000 ALTER TABLE `responsaveis` DISABLE KEYS */;
INSERT INTO `responsaveis` VALUES (1,'Gesiane Monteiro','Processos',1,'2026-04-13 09:54:34','2026-04-13 09:57:14'),(2,'ALISSON JORGE','Utilidades',1,'2026-04-13 09:54:34','2026-04-13 09:57:26'),(4,'Thalmo Fernandes','General Services',1,'2026-04-13 10:21:28','2026-04-13 10:21:28');
/*!40000 ALTER TABLE `responsaveis` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `rugosidade_itens`
--

DROP TABLE IF EXISTS `rugosidade_itens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `rugosidade_itens` (
  `id` int NOT NULL AUTO_INCREMENT,
  `lancamento_id` int NOT NULL,
  `modelo_codigo` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `valor_rugosidade` float DEFAULT NULL,
  `limite_referencia` float NOT NULL DEFAULT '14',
  `fora_padrao` tinyint(1) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_rugosidade_lancamento_modelo` (`lancamento_id`,`modelo_codigo`),
  KEY `ix_rugosidade_itens_lancamento_id` (`lancamento_id`),
  KEY `ix_rugosidade_itens_modelo_codigo` (`modelo_codigo`),
  CONSTRAINT `rugosidade_itens_ibfk_1` FOREIGN KEY (`lancamento_id`) REFERENCES `rugosidade_lancamentos` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `rugosidade_itens`
--

LOCK TABLES `rugosidade_itens` WRITE;
/*!40000 ALTER TABLE `rugosidade_itens` DISABLE KEYS */;
INSERT INTO `rugosidade_itens` VALUES (1,1,'521',12,14,0,'2026-04-13 13:20:55','2026-04-13 13:20:55'),(2,1,'226',12,14,0,'2026-04-13 13:20:55','2026-04-13 13:20:55'),(3,1,'551',11,14,0,'2026-04-13 13:20:55','2026-04-13 13:20:55'),(4,1,'598',16,14,1,'2026-04-13 13:20:55','2026-04-13 13:20:55'),(5,1,'291',15,14,1,'2026-04-13 13:20:55','2026-04-13 13:20:55');
/*!40000 ALTER TABLE `rugosidade_itens` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `rugosidade_lancamentos`
--

DROP TABLE IF EXISTS `rugosidade_lancamentos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `rugosidade_lancamentos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `data_referencia` date NOT NULL,
  `sequencia` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `responsavel_nome` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'rascunho',
  `observacoes_gerais` text COLLATE utf8mb4_unicode_ci,
  `total_modelos_fora_padrao` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_rugosidade_lancamentos_data_referencia` (`data_referencia`),
  KEY `ix_rugosidade_lancamentos_sequencia` (`sequencia`),
  KEY `ix_rugosidade_lancamentos_status` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `rugosidade_lancamentos`
--

LOCK TABLES `rugosidade_lancamentos` WRITE;
/*!40000 ALTER TABLE `rugosidade_lancamentos` DISABLE KEYS */;
INSERT INTO `rugosidade_lancamentos` VALUES (1,'2026-04-13','1','ALISSON JORGE','concluido',NULL,2,'2026-04-13 13:20:55','2026-04-13 13:21:22');
/*!40000 ALTER TABLE `rugosidade_lancamentos` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `setores`
--

DROP TABLE IF EXISTS `setores`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `setores` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nome` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sigla` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ativo` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `nome` (`nome`),
  UNIQUE KEY `sigla` (`sigla`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `setores`
--

LOCK TABLES `setores` WRITE;
/*!40000 ALTER TABLE `setores` DISABLE KEYS */;
INSERT INTO `setores` VALUES (1,'Laboratório','LAB',1,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(2,'PT/ED','PTED',1,'2026-04-13 09:54:34','2026-04-13 09:54:34'),(3,'Fornecedor','FORN',1,'2026-04-13 09:54:34','2026-04-13 09:54:34');
/*!40000 ALTER TABLE `setores` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `temperatura_forno_itens`
--

DROP TABLE IF EXISTS `temperatura_forno_itens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `temperatura_forno_itens` (
  `id` int NOT NULL AUTO_INCREMENT,
  `lancamento_id` int NOT NULL,
  `zona_numero` int NOT NULL,
  `valor_temperatura` float DEFAULT NULL,
  `faixa_min` float NOT NULL,
  `faixa_max` float NOT NULL,
  `fora_padrao` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_temperatura_forno_lancamento_zona` (`lancamento_id`,`zona_numero`),
  KEY `ix_temperatura_forno_itens_lancamento_id` (`lancamento_id`),
  KEY `ix_temperatura_forno_itens_zona_numero` (`zona_numero`),
  CONSTRAINT `temperatura_forno_itens_ibfk_1` FOREIGN KEY (`lancamento_id`) REFERENCES `temperatura_forno_lancamentos` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `temperatura_forno_itens`
--

LOCK TABLES `temperatura_forno_itens` WRITE;
/*!40000 ALTER TABLE `temperatura_forno_itens` DISABLE KEYS */;
/*!40000 ALTER TABLE `temperatura_forno_itens` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `temperatura_forno_lancamentos`
--

DROP TABLE IF EXISTS `temperatura_forno_lancamentos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `temperatura_forno_lancamentos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `data_referencia` date NOT NULL,
  `responsavel_nome` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'rascunho',
  `observacoes_gerais` text COLLATE utf8mb4_unicode_ci,
  `total_zonas_fora_padrao` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_temperatura_forno_lancamentos_data_referencia` (`data_referencia`),
  KEY `ix_temperatura_forno_lancamentos_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `temperatura_forno_lancamentos`
--

LOCK TABLES `temperatura_forno_lancamentos` WRITE;
/*!40000 ALTER TABLE `temperatura_forno_lancamentos` DISABLE KEYS */;
/*!40000 ALTER TABLE `temperatura_forno_lancamentos` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tensao_retificadores_itens`
--

DROP TABLE IF EXISTS `tensao_retificadores_itens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tensao_retificadores_itens` (
  `id` int NOT NULL AUTO_INCREMENT,
  `lancamento_id` int NOT NULL,
  `zona_numero` int NOT NULL,
  `valor_tensao` float DEFAULT NULL,
  `fora_padrao` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_tensao_retificadores_lancamento_zona` (`lancamento_id`,`zona_numero`),
  KEY `ix_tensao_retificadores_itens_lancamento_id` (`lancamento_id`),
  KEY `ix_tensao_retificadores_itens_zona_numero` (`zona_numero`),
  CONSTRAINT `tensao_retificadores_itens_ibfk_1` FOREIGN KEY (`lancamento_id`) REFERENCES `tensao_retificadores_lancamentos` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=30 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tensao_retificadores_itens`
--

LOCK TABLES `tensao_retificadores_itens` WRITE;
/*!40000 ALTER TABLE `tensao_retificadores_itens` DISABLE KEYS */;
INSERT INTO `tensao_retificadores_itens` VALUES (1,1,1,222,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(2,1,2,222,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(3,1,3,222,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(4,1,4,222,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(5,1,5,222,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(6,1,6,122,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(7,1,7,122,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(8,1,8,122,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(9,1,9,122,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(10,1,10,322,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(11,1,11,NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(12,1,12,NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(13,1,13,NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(14,1,14,NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(15,1,15,NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(16,1,16,NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(17,1,17,NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(18,1,18,NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(19,1,19,NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(20,1,20,NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(21,1,21,NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(22,1,22,NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(23,1,23,NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(24,1,24,NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(25,1,25,NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(26,1,26,NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(27,1,27,NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(28,1,28,NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34'),(29,1,29,NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34');
/*!40000 ALTER TABLE `tensao_retificadores_itens` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tensao_retificadores_lancamentos`
--

DROP TABLE IF EXISTS `tensao_retificadores_lancamentos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tensao_retificadores_lancamentos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `data_referencia` date NOT NULL,
  `turno` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `modelo` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `responsavel_nome` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'rascunho',
  `observacoes_gerais` text COLLATE utf8mb4_unicode_ci,
  `total_zonas_fora_padrao` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_tensao_retificadores_lancamentos_data_referencia` (`data_referencia`),
  KEY `ix_tensao_retificadores_lancamentos_turno` (`turno`),
  KEY `ix_tensao_retificadores_lancamentos_modelo` (`modelo`),
  KEY `ix_tensao_retificadores_lancamentos_status` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tensao_retificadores_lancamentos`
--

LOCK TABLES `tensao_retificadores_lancamentos` WRITE;
/*!40000 ALTER TABLE `tensao_retificadores_lancamentos` DISABLE KEYS */;
INSERT INTO `tensao_retificadores_lancamentos` VALUES (1,'2026-04-13','1','5665','ALISSON JORGE','rascunho',NULL,0,'2026-04-13 12:11:34','2026-04-13 12:11:34');
/*!40000 ALTER TABLE `tensao_retificadores_lancamentos` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `turnos`
--

DROP TABLE IF EXISTS `turnos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `turnos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nome` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `codigo` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ativo` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `nome` (`nome`),
  UNIQUE KEY `codigo` (`codigo`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `turnos`
--

LOCK TABLES `turnos` WRITE;
/*!40000 ALTER TABLE `turnos` DISABLE KEYS */;
INSERT INTO `turnos` VALUES (6,'2º Turno','2',1,'2026-04-13 09:54:34','2026-04-13 10:23:38'),(8,'1º Turno','1',1,'2026-04-13 09:54:34','2026-04-13 10:23:26'),(11,'3º Turno','3',1,'2026-04-13 10:23:48','2026-04-13 10:23:48'),(12,'ADM','ADM',1,'2026-04-13 13:51:56','2026-04-13 13:51:56');
/*!40000 ALTER TABLE `turnos` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-04-16 15:20:40
