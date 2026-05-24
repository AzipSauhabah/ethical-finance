-- LEI CAC40 manquants — récupérés via GLEIF API le 2026-05-24
INSERT INTO ticker_lei_mapping (ticker, lei, legal_name, source) VALUES
('VK.PA',    '969500P2Q1B47H4MCJ34', 'Vallourec S.A.',    'GLEIF'),
('DG.PA',    '969500ACWTMYEQHTNG39', 'Vinci S.A.',         'GLEIF'),
('BN.PA',    '969500KMUQ2B6CBAF162', 'Danone S.A.',        'GLEIF'),
('RNO.PA',   '969500F7JLTX36OUI695', 'Renault S.A.',       'GLEIF'),
('SW.PA',    '969500S4G72RJY9UD479', 'Sodexo S.A.',        'GLEIF'),
('MT.AS',    '2EULGUTUI56JI9SAL165', 'ArcelorMittal S.A.', 'GLEIF'),
('BOL.PA',   '969500LEKCHH6VV86P94', 'Bollore SE',         'GLEIF'),
('ATO.PA',   '967600KS6B4E8WOCB679', 'Atos SE',            'GLEIF'),
('STLAM.MI', '969500UHVEKG6HEC9V34', 'Stellantis N.V.',    'GLEIF')
ON CONFLICT (ticker) DO UPDATE SET lei=EXCLUDED.lei, legal_name=EXCLUDED.legal_name, source=EXCLUDED.source;
