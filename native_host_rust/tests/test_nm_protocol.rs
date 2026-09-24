//! Native Messaging Protocol Unit Tests
//! Tests message serialization/deserialization and protocol encoding

#[cfg(test)]
mod tests {
    use serde_json;

    /// Simulated NM message types for testing
    #[derive(Debug, Clone, serde::Deserialize, serde::Serialize, PartialEq)]
    #[serde(tag = "type", rename_all = "snake_case")]
    enum TestNmMessage {
        Translate {
            text: String,
            #[serde(default)]
            source_lang: Option<String>,
            #[serde(default)]
            target_lang: Option<String>,
        },
        Ocr {
            data_url: String,
            #[serde(default)]
            timeout_ms: Option<u64>,
        },
        GetVersion,
        Ping {
            #[serde(default)]
            timestamp: Option<u64>,
        },
        #[serde(other)]
        Unknown,
    }

    #[derive(Debug, Clone, serde::Serialize, serde::Deserialize, PartialEq)]
    #[serde(tag = "type", rename_all = "snake_case")]
    enum TestNmResponse {
        Translate {
            text: String,
        },
        Version {
            protocol_version: String,
            app_version: String,
        },
        Pong {
            timestamp: u64,
        },
        Error {
            code: String,
            message: String,
        },
    }

    /// Encode a message to NM protocol format (4-byte LE length + UTF-8 JSON)
    fn encode_message(msg: &TestNmMessage) -> Vec<u8> {
        let json = serde_json::to_vec(msg).unwrap();
        let len = (json.len() as u32).to_le_bytes();
        let mut result = Vec::with_capacity(4 + json.len());
        result.extend_from_slice(&len);
        result.extend_from_slice(&json);
        result
    }

    /// Decode a message from NM protocol format
    fn decode_message(data: &[u8]) -> Result<TestNmMessage, String> {
        if data.len() < 4 {
            return Err("Data too short".to_string());
        }
        let len = u32::from_le_bytes([data[0], data[1], data[2], data[3]]) as usize;
        if data.len() < 4 + len {
            return Err("Incomplete message".to_string());
        }
        serde_json::from_slice(&data[4..4 + len]).map_err(|e| e.to_string())
    }

    #[test]
    fn test_encode_decode_translate() {
        let msg = TestNmMessage::Translate {
            text: "Hello World".to_string(),
            source_lang: Some("en".to_string()),
            target_lang: Some("zh".to_string()),
        };

        let encoded = encode_message(&msg);
        assert!(encoded.len() > 4);

        // Verify length prefix
        let len = u32::from_le_bytes([encoded[0], encoded[1], encoded[2], encoded[3]]);
        assert_eq!(len as usize, encoded.len() - 4);

        // Decode and verify
        let decoded = decode_message(&encoded).unwrap();
        assert_eq!(decoded, msg);
    }

    #[test]
    fn test_encode_decode_ocr() {
        let msg = TestNmMessage::Ocr {
            data_url: "data:image/png;base64,ABC123".to_string(),
            timeout_ms: Some(5000),
        };

        let encoded = encode_message(&msg);
        let decoded = decode_message(&encoded).unwrap();
        assert_eq!(decoded, msg);
    }

    #[test]
    fn test_encode_decode_ping() {
        let msg = TestNmMessage::Ping {
            timestamp: Some(1234567890),
        };

        let encoded = encode_message(&msg);
        let decoded = decode_message(&encoded).unwrap();
        assert_eq!(decoded, msg);
    }

    #[test]
    fn test_encode_decode_get_version() {
        let msg = TestNmMessage::GetVersion;

        let encoded = encode_message(&msg);
        let decoded = decode_message(&encoded).unwrap();
        assert_eq!(decoded, msg);
    }

    #[test]
    fn test_unknown_message_type() {
        let json = r#"{"type": "unknown_type", "data": "test"}"#;
        let result: Result<TestNmMessage, _> = serde_json::from_str(json);
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), TestNmMessage::Unknown);
    }

    #[test]
    fn test_decode_response_translate() {
        let json = r#"{"type": "translate", "text": "你好世界"}"#;
        let resp: TestNmResponse = serde_json::from_str(json).unwrap();
        assert_eq!(
            resp,
            TestNmResponse::Translate {
                text: "你好世界".to_string()
            }
        );
    }

    #[test]
    fn test_decode_response_version() {
        let json = r#"{"type": "version", "protocol_version": "1.0.0", "app_version": "0.1.0"}"#;
        let resp: TestNmResponse = serde_json::from_str(json).unwrap();
        assert_eq!(
            resp,
            TestNmResponse::Version {
                protocol_version: "1.0.0".to_string(),
                app_version: "0.1.0".to_string(),
            }
        );
    }

    #[test]
    fn test_decode_response_pong() {
        let json = r#"{"type": "pong", "timestamp": 1234567890}"#;
        let resp: TestNmResponse = serde_json::from_str(json).unwrap();
        assert_eq!(
            resp,
            TestNmResponse::Pong {
                timestamp: 1234567890
            }
        );
    }

    #[test]
    fn test_decode_response_error() {
        let json = r#"{"type": "error", "code": "TRANSLATE_ERROR", "message": "API key missing"}"#;
        let resp: TestNmResponse = serde_json::from_str(json).unwrap();
        assert_eq!(
            resp,
            TestNmResponse::Error {
                code: "TRANSLATE_ERROR".to_string(),
                message: "API key missing".to_string(),
            }
        );
    }

    #[test]
    fn test_empty_message_fails() {
        let data = vec![0u8; 4]; // Length = 0
        let result = decode_message(&data);
        assert!(result.is_err());
    }

    #[test]
    fn test_incomplete_message_fails() {
        let mut data = vec![0u8; 4];
        data[0] = 10; // Claims 10 bytes but only 4
        let result = decode_message(&data);
        assert!(result.is_err());
    }

    #[test]
    fn test_large_message() {
        // Test with a large text message
        let large_text = "A".repeat(100_000);
        let msg = TestNmMessage::Translate {
            text: large_text.clone(),
            source_lang: None,
            target_lang: None,
        };

        let encoded = encode_message(&msg);
        assert!(encoded.len() > 100_000);
        let decoded = decode_message(&encoded).unwrap();
        assert_eq!(decoded, msg);
    }

    #[test]
    fn test_unicode_message() {
        let msg = TestNmMessage::Translate {
            text: "Hello 世界 🌍".to_string(),
            source_lang: Some("en".to_string()),
            target_lang: Some("zh".to_string()),
        };

        let encoded = encode_message(&msg);
        let decoded = decode_message(&encoded).unwrap();
        assert_eq!(decoded, msg);
    }

    #[test]
    fn test_missing_optional_fields() {
        // Test message without optional fields
        let json = r#"{"type": "translate", "text": "Hello"}"#;
        let msg: TestNmMessage = serde_json::from_str(json).unwrap();
        assert_eq!(
            msg,
            TestNmMessage::Translate {
                text: "Hello".to_string(),
                source_lang: None,
                target_lang: None,
            }
        );
    }

    #[test]
    fn test_protocol_roundtrip() {
        let messages = vec![
            TestNmMessage::GetVersion,
            TestNmMessage::Ping { timestamp: None },
            TestNmMessage::Ping {
                timestamp: Some(1234567890),
            },
            TestNmMessage::Translate {
                text: "Test".to_string(),
                source_lang: None,
                target_lang: None,
            },
            TestNmMessage::Ocr {
                data_url: "data:image/png;base64,test".to_string(),
                timeout_ms: None,
            },
        ];

        for msg in messages {
            let encoded = encode_message(&msg);
            let decoded = decode_message(&encoded).unwrap();
            assert_eq!(decoded, msg);
        }
    }
}
