package com.example.transfer;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import javax.crypto.Cipher;
import java.io.FileReader;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.time.Instant;
import java.util.*;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Base64;
import java.io.ByteArrayInputStream;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import okhttp3.Headers;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import java.util.concurrent.TimeUnit;

/**
 * 商家转账-发起转账API实现类
 */
public class CreateTransfer {
    private static final String HOST = "https://api.mch.weixin.qq.com";
    private static final String PATH = "/v3/fund-app/mch-transfer/transfer-bills";
    private static final String METHOD = "POST";

    // 商户相关配置
    private final String mchId = "1900006891"; // 商户号
    private final String privateKeySerialNo = "XXXXXXX"; // 商户API证书序列号
    private final String privateKeyFilepath = "XXXXX/apiclient_key.pem"; // 商户API证书私钥文件路径
    private final String publicKeySerialNo = "XXXXXXXX"; // 微信支付平台证书序列号
    private final String publicKeyFilepath = "XXXXX/apiclient_cert.pem"; // 微信支付平台证书文件路径

    private PrivateKey privateKey;
    private PublicKey publicKey;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public CreateTransfer() {
        loadKeysFromFile();
    }

    /**
     * 加载商户API证书私钥和微信支付公钥
     */
    private void loadKeysFromFile() {
        try {
            // 加载商户API证书私钥
            String privateKeyContent = new String(Files.readAllBytes(Paths.get(privateKeyFilepath)));
            String privateKey = privateKeyContent.replace("-----BEGIN PRIVATE KEY-----", "")
                    .replace("-----END PRIVATE KEY-----", "")
                    .replaceAll("\\s+", "");

            KeyFactory kf = KeyFactory.getInstance("RSA");
            this.privateKey = kf.generatePrivate(
                    new PKCS8EncodedKeySpec(Base64.getDecoder().decode(privateKey)));

            // 加载微信支付平台证书
            byte[] certBytes = Files.readAllBytes(Paths.get(publicKeyFilepath));
            CertificateFactory cf = CertificateFactory.getInstance("X.509");
            X509Certificate cert = (X509Certificate) cf.generateCertificate(new ByteArrayInputStream(certBytes));
            this.publicKey = cert.getPublicKey();
        } catch (Exception e) {
            e.printStackTrace();
            throw new RuntimeException("Failed to load keys", e);
        }
    }

    /**
     * 商家转账-发起转账
     * 
     * 重要说明：
     * 1. 同一笔转账订单的商户订单号重入时，请求参数需要保持一致
     * 2. 当HTTP状态码为5XX或429时，可以尝试重试，但必须使用原商户订单号
     * 3. 敏感信息加密时需要使用【微信支付公钥】
     * 4. 建议在调用接口前检查商户账户余额是否充足
     */
    public Map<String, Object> createTransferOrder() throws Exception {
        // 1. 构造请求包体
        Map<String, Object> requestBody = makeRequestBody();

        // // 2. 验证请求包体
        // validateRequestBody(requestBody);

        // 3. 发送请求
        HttpResponse response = sendRequest(requestBody);

        // 4. 解析HTTP状态码
        checkStatusCode(response);

        // 5. 验证HTTP响应结果
        validateResponse(response);

        // 6. 解析HTTP响应结果
        return parseResponse(response);
    }

    /**
     * 构造请求参数
     */
    private Map<String, Object> makeRequestBody() throws Exception {
        Map<String, Object> body = new HashMap<>();
        body.put("appid", "XXXXX"); // 商户号绑定的appid
        body.put("out_bill_no", "XXXXX"); // 商户系统内部的商家单号
        body.put("transfer_scene_id", "1000"); // 转账场景ID
        body.put("openid", "XXXXX"); // 用户openid
        body.put("user_name", encrypt("XXXX")); // 当转账金额>=2000元时必填，需要使用公钥加密
        body.put("transfer_amount", 400000); // 转账金额，单位为分
        body.put("transfer_remark", "2020年4月报销"); // 转账备注
        body.put("notify_url", "https://XXXXX"); // 回调通知地址
        body.put("user_recv_perception", "现金奖励"); // 用户收款感知

        // 转账报备信息
        List<Map<String, String>> reportInfos = new ArrayList<>();
        Map<String, String> info1 = new HashMap<>();
        info1.put("info_type", "活动名称");
        info1.put("info_content", "新会员有礼");
        Map<String, String> info2 = new HashMap<>();
        info2.put("info_type", "奖励说明");
        info2.put("info_content", "注册会员抽奖一等奖");
        reportInfos.add(info1);
        reportInfos.add(info2);
        body.put("transfer_scene_report_infos", reportInfos);

        return body;
    }

    /**
     * 验证请求参数
     */
    private void validateRequestBody(Map<String, Object> transferData) {
        // TODO: 实现验证请求参数的逻辑
        throw new UnsupportedOperationException("This method needs to be implemented");
    }

    /**
     * 发送HTTP请求
     */
    private HttpResponse sendRequest(Map<String, Object> body) throws Exception {
        String bodyStr = objectMapper.writeValueAsString(body);
        Map<String, String> headers = makeRequestHeader(bodyStr);

        OkHttpClient client = new OkHttpClient.Builder()
                .connectTimeout(10, TimeUnit.SECONDS)
                .writeTimeout(10, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .build();

        Request request = new Request.Builder()
                .url(HOST + PATH)
                .post(RequestBody.create(bodyStr, MediaType.parse("application/json")))
                .headers(Headers.of(headers))
                .build();

        try (Response response = client.newCall(request).execute()) {
            HttpResponse httpResponse = new HttpResponse();
            httpResponse.statusCode = response.code();
            httpResponse.headers = new HashMap<>();
            response.headers().forEach(header -> httpResponse.headers.put(header.getFirst(), header.getSecond()));
            httpResponse.body = response.body().string();
            return httpResponse;
        }
    }

    /**
     * 构造请求头（包含签名）
     */
    private Map<String, String> makeRequestHeader(String bodyStr) throws Exception {
        Map<String, Object> signData = generateSign(METHOD, PATH, bodyStr);

        Map<String, String> headers = new HashMap<>();
        headers.put("Content-Type", "application/json");
        headers.put("Accept", "application/json");
        headers.put("Wechatpay-Serial", publicKeySerialNo);
        headers.put("Authorization", String.format(
                "WECHATPAY2-SHA256-RSA2048 mchid=\"%s\",nonce_str=\"%s\",timestamp=\"%s\",serial_no=\"%s\",signature=\"%s\"",
                mchId, signData.get("nonce"), signData.get("timestamp"), privateKeySerialNo,
                signData.get("signature")));

        return headers;
    }

    /**
     * 生成请求签名
     */
    private Map<String, Object> generateSign(String method, String path, String bodyStr) throws Exception {
        long timestamp = Instant.now().getEpochSecond();
        String nonce = UUID.randomUUID().toString();
        String message = String.format("%s\n%s\n%s\n%s\n%s\n", method, path, timestamp, nonce, bodyStr);

        Signature signature = Signature.getInstance("SHA256withRSA");
        signature.initSign(privateKey);
        signature.update(message.getBytes(StandardCharsets.UTF_8));
        String sign = Base64.getEncoder().encodeToString(signature.sign());

        Map<String, Object> signData = new HashMap<>();
        signData.put("timestamp", timestamp);
        signData.put("nonce", nonce);
        signData.put("signature", sign);
        return signData;
    }

    /**
     * 检查HTTP状态码
     */
    private void checkStatusCode(HttpResponse response) {
        int statusCode = response.getStatusCode();
        if (statusCode >= 200 && statusCode < 300) {
            return;
        }
        throw new RuntimeException("HTTP 状态码异常: " + statusCode);
    }

    /**
     * 验证响应签名
     */
    private void validateResponse(HttpResponse response) throws Exception {
        // TODO: 实现验证响应签名的逻辑
        throw new UnsupportedOperationException("This method needs to be implemented");
    }

    /**
     * 解析响应结果
     */
    private Map<String, Object> parseResponse(HttpResponse response) throws Exception {
        // TODO: 实现解析响应结果的逻辑
        throw new UnsupportedOperationException("This method needs to be implemented");
    }

    /**
     * 使用公钥加密敏感信息
     */
    private String encrypt(String data) throws Exception {
        Cipher cipher = Cipher.getInstance("RSA/ECB/OAEPWithSHA-1AndMGF1Padding", new BouncyCastleProvider());
        cipher.init(Cipher.ENCRYPT_MODE, publicKey);
        byte[] encryptedData = cipher.doFinal(data.getBytes(StandardCharsets.UTF_8));
        return Base64.getEncoder().encodeToString(encryptedData);
    }

    // 为了示例完整性，这里定义一个简单的 HttpResponse 类
    private static class HttpResponse {
        private int statusCode;
        private Map<String, String> headers;
        private String body;

        public int getStatusCode() {
            return statusCode;
        }

        public Map<String, String> getHeaders() {
            return headers;
        }

        public String getBody() {
            return body;
        }
    }

    public static void main(String[] args) {
        try {
            CreateTransfer transfer = new CreateTransfer();
            Map<String, Object> result = transfer.createTransferOrder();
            System.out.println("Transfer result: " + result);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}