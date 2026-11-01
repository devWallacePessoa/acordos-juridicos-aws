-- =============================================================================
-- Queries Analíticas e Gerenciais - Plataforma de Acordos Jurídicos
-- =============================================================================

-- 1. Resumo executivo por Autor: total de acordos, total de documentos e média de documentos por acordo
SELECT
    au.id AS autor_id,
    au.nome AS autor_nome,
    au.email AS autor_email,
    au.empresa_nome,
    au.empresa_segmento,
    COUNT(DISTINCT ac.id) AS total_acordos,
    COUNT(doc.id) AS total_documentos,
    ROUND(
        CASE
            WHEN COUNT(DISTINCT ac.id) > 0 THEN COUNT(doc.id)::NUMERIC / COUNT(DISTINCT ac.id)
            ELSE 0
        END, 2
    ) AS media_documentos_por_acordo
FROM autores au
LEFT JOIN acordos ac ON ac.autor_id = au.id
LEFT JOIN documentos doc ON doc.acordo_id = ac.id
GROUP BY au.id, au.nome, au.email, au.empresa_nome, au.empresa_segmento
ORDER BY total_acordos DESC, total_documentos DESC;

-- 2. Ranking dos Acordos com maior volume de documentos comprobatórios anexados
SELECT
    ac.id AS acordo_id,
    ac.titulo AS acordo_titulo,
    au.id AS autor_id,
    au.nome AS autor_nome,
    COUNT(doc.id) AS quantidade_documentos,
    DENSE_RANK() OVER (ORDER BY COUNT(doc.id) DESC) AS ranking_volume_documental
FROM acordos ac
INNER JOIN autores au ON au.id = ac.autor_id
LEFT JOIN documentos doc ON doc.acordo_id = ac.id
GROUP BY ac.id, ac.titulo, au.id, au.nome
ORDER BY quantidade_documentos DESC, ac.id ASC
LIMIT 20;

-- 3. Distribuição de litígios e acordos por Segmento Empresarial do Autor
SELECT
    au.empresa_segmento AS segmento_empresarial,
    COUNT(DISTINCT au.id) AS qtd_autores,
    COUNT(DISTINCT ac.id) AS qtd_acordos,
    COUNT(doc.id) AS qtd_documentos,
    ROUND(
        (COUNT(DISTINCT ac.id)::NUMERIC / NULLIF(SUM(COUNT(DISTINCT ac.id)) OVER (), 0)) * 100,
        2
    ) AS percentual_acordos
FROM autores au
LEFT JOIN acordos ac ON ac.autor_id = au.id
LEFT JOIN documentos doc ON doc.acordo_id = ac.id
GROUP BY au.empresa_segmento
ORDER BY qtd_acordos DESC;

-- 4. Auditoria de integridade: Acordos sem documentos vinculados (alerta operacional jurídico)
SELECT
    ac.id AS acordo_id,
    ac.titulo AS acordo_titulo,
    au.id AS autor_id,
    au.nome AS autor_nome,
    au.email AS autor_email,
    ac.criado_em
FROM acordos ac
INNER JOIN autores au ON au.id = ac.autor_id
LEFT JOIN documentos doc ON doc.acordo_id = ac.id
WHERE doc.id IS NULL
ORDER BY ac.criado_em DESC;

-- 5. Consulta consolidada em formato JSON (compatível com o payload da API de Consulta de Acordos)
SELECT
    jsonb_build_object(
        'autor', jsonb_build_object(
            'id', au.id,
            'nome', au.nome,
            'email', au.email,
            'telefone', au.telefone,
            'endereco', au.endereco,
            'empresa', jsonb_build_object(
                'nome', au.empresa_nome,
                'segmento', au.empresa_segmento
            )
        ),
        'acordos', COALESCE(
            (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'id', ac.id,
                        'titulo', ac.titulo,
                        'documentos', COALESCE(
                            (
                                SELECT jsonb_agg(
                                    jsonb_build_object(
                                        'id', doc.id,
                                        'titulo', doc.titulo,
                                        'url', doc.url,
                                        'thumbnailUrl', doc.thumbnail_url
                                    ) ORDER BY doc.id
                                )
                                FROM documentos doc
                                WHERE doc.acordo_id = ac.id
                            ),
                            '[]'::jsonb
                        )
                    ) ORDER BY ac.id
                )
                FROM acordos ac
                WHERE ac.autor_id = au.id
            ),
            '[]'::jsonb
        )
    ) AS payload_consolidado
FROM autores au
ORDER BY au.id;
