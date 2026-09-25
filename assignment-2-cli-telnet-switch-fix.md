# รายงานการวิเคราะห์ปัญหาและแนวทางแก้ไขระบบ Assignment 2 (NetConfig Tracer Studio)

เอกสารฉบับนี้จัดทำขึ้นเพื่อขยายความและระบุสาเหตุเชิงลึกของปัญหา 2 ข้อหลักที่เกิดขึ้นในการใช้งานระบบ Network Automation Web Application พร้อมแนวทางการแก้ไขเชิงระบบ และชุดทดสอบ (Tester Suite)

---

## 1. ปัญหาข้อที่ 1: CLI Terminal ไม่แสดงข้อมูลจริงจากอุปกรณ์ (CLI Real Data Issue)

### 1.1 ปรากฏการณ์ที่พบ (Symptoms)
1. เมื่อผู้ใช้พิมพ์คำสั่งผ่านหน้าต่าง Console / CLI Terminal (เช่น `show ip interface brief`, `show ip route`, `show version`, `configure terminal` ฯลฯ) ข้อมูลที่แสดงผลในหลายกรณีเป็นข้อมูลจำลอง (Mock / Simulated Data) หรือแสดงผลไม่ตรงกับสถานะจริงของ Router/Switch
2. บางครั้งคำสั่งถูกตัดขาด (Truncated) หรือไม่แสดงข้อความตอบกลับจากอุปกรณ์จริง หรือแสดงผลเป็นช่องว่าง
3. Prompt บนหน้าต่าง Terminal (เช่น `R1#`, `R1(config)#`) ไม่เปลี่ยนตามโหมดจริงที่อุปกรณ์อยู่ในขณะนั้น (เช่น เมื่อเข้า `config t` หรือ `interface GigabitEthernet0/1` แต่ Prompt บนหน้าจอยังเป็น `R1#`)
4. เมื่อสั่ง Deploy คอนฟิกจากเมนู GUI (เช่น Interface Config, Routing Config) ข้อมูลผลลัพธ์จากอุปกรณ์ไม่ถูกส่งต่อมาแสดงในกล่อง Console ด้านล่าง และพบ JavaScript Error `ReferenceError: appendConsole is not defined` ในเบราว์เซอร์

### 1.2 สาเหตุเชิงลึก (Root Cause Analysis)

#### ก. การใช้ `_demo_show` และการจำลอง Hardcoded Mock แทนการดึงข้อมูลจาก Session จริง
ในโค้ดเดิม หากอุปกรณ์ไม่ได้เชื่อมต่อหรือเกิดความผิดพลาดในการค้นหา Device ID ฟังก์ชันใน backend (`app.py`) จะตัดเข้าสู่ `_demo_show` ซึ่งเป็นฟังก์ชันที่สร้างข้อความหลอกขึ้นมา เช่น:
```python
# โค้ดเดิมใน app.py
if conn_mgr.is_connected(device_id):
    result = conn_mgr.send_command(device_id, command)
else:
    output = _demo_show(device_id, command)  # ส่งข้อมูลปลอมกลับไป
```
ทำให้ผู้ใช้เข้าใจว่ากำลังสั่งการอุปกรณ์จริง ทั้งที่คำสั่งไม่ได้ถูกส่งไปยัง Session ของ Router หรือ Switch เลย

#### ข. ปัญหาในฟังก์ชัน `send_interactive` ของ `ConnectionManager`
ใน connection_manager.py ฟังก์ชัน `send_interactive()` เดิมใช้คำสั่ง:
```python
handler.write_channel(cmd_to_send)
raw = handler.read_channel_timing(last_read=0.5, read_timeout=8.0)
```
จุดบกพร่องที่ร้ายแรงคือ:
- `last_read=0.5` สั้นเกินไปอย่างมากสำหรับอุปกรณ์เครือข่ายจริงหรือ EVE-NG เมื่อส่งคำสั่งที่ต้องใช้เวลาประมวลผล เช่น `show running-config` หรือ `ping` อุปกรณ์จะหยุดส่งข้อมูลชั่วขณะเกิน 0.5 วินาที ทำให้ `read_channel_timing` ยุติการอ่านก่อนที่ข้อมูลจริงจะส่งมาครบ
- ข้อมูลที่เหลือของคำสั่งเดิมจะตกค้างอยู่ใน Buffer ของ Telnet/SSH Socket เมื่อผู้ใช้ส่งคำสั่งถัดไป ข้อมูลตกค้างเดิมจะทะลักออกมาปะปน ทำให้ผลลัพธ์ของคำสั่งใหม่กลายเป็นผลลัพธ์ของคำสั่งเก่า
- ไม่มีการสั่ง `terminal length 0` และ `terminal width 512` ซ้ำก่อนเข้า CLI ทำให้หากอุปกรณ์มีบรรทัดยาว จะเกิด `--More--` ค้างอยู่ใน Socket จนระบบค้าง

#### ค. บั๊ก `appendConsole` หายไปใน Frontend JavaScript
ใน static/js/app.js มีการเรียกใช้งานฟังก์ชัน `appendConsole(...)` ถึง 8 จุด (เช่น ใน `onActiveDeviceChange`, `applyInterfaceConfig`, `applyRoutingConfig`) แต่ตัวฟังก์ชัน `appendConsole` กลับไม่ได้ถูกนิยามไว้ ส่งผลให้ JavaScript เกิด Uncaught Exception ทันที และข้อความตอบกลับจากอุปกรณ์จริงไม่สามารถนำมาแสดงใน Console ได้

---

## 2. ปัญหาข้อที่ 2: Telnet กับ Switch เกิด Connection Loss (Disconnect / Drop)

### 2.1 ปรากฏการณ์ที่พบ (Symptoms)
1. เมื่อทำการเชื่อมต่อกับ Switch ผ่านโปรโตคอล Telnet (เช่น S1 พอร์ต 23 หรือ EVE-NG Port) การเชื่อมต่อมักจะหลุดหลังจากผ่านไปสักครู่ (Idle Timeout)
2. เมื่อ Session หลุดไปแล้ว หน้าเว็บยังคงแสดงสถานะว่าอุปกรณ์เชื่อมต่ออยู่ (`is_connected = True`)
3. เมื่อผู้ใช้พยายามส่งคำสั่งใดๆ ไปยัง Switch หลังจากนั้น ระบบจะเกิด Exception เช่น:
   - `EOFError`
   - `ConnectionResetError: [WinError 10054] An existing connection was forcibly closed by the remote host`
   - `socket.error: [Errno 32] Broken pipe`
4. เมื่อเกิดข้อผิดพลาดขึ้นใน `send_interactive` ระบบไม่มีการพยายามเชื่อมต่อใหม่ (Auto-Reconnect) ทำให้ session ตายถาวรและไม่สามารถใช้งาน Switch ได้อีกจนกว่าจะรีสตาร์ทแอปหรือกด Disconnect/Connect ซ้ำด้วยตนเอง

### 2.2 สาเหตุเชิงลึก (Root Cause Analysis)

#### ก. Cisco IOS Switch Inactivity / EXEC Timeout
บน Cisco Switch (ทั้ง Physical Catalyst, Cisco IOU L2, และ IOSvL2 บน EVE-NG) ค่าคอนฟิกเริ่มต้นของ Line VTY และ Console มักจะมี `exec-timeout 5 0` (5 นาที) หรือในบางแล็บสั้นเพียง 1-2 นาที หากไม่มีทราฟฟิกข้อมูลส่งผ่าน Telnet TCP Socket ตัว Switch จะส่งแพ็กเก็ต TCP FIN/RST เพื่อปิด Connection ทิ้งทันที

#### ข. ConnectionManager `is_connected()` ทำงานแบบ Blind Check
ฟังก์ชันตรวจสอบสถานะเดิมใน `ConnectionManager`:
```python
def is_connected(self, device_id: str) -> bool:
    if device_id in self.pool:
        return True
    ...
```
ฟังก์ชันนี้เพียงแค่ตรวจว่ามี key อยู่ใน Dictionary `self.pool` หรือไม่ **โดยไม่เคยตรวจสอบเลยว่า Socket ของ TCP Telnet ยังเปิดอยู่จริงหรือไม่** แม้ว่า Switch จะตัดสายทิ้งไปแล้ว `is_connected()` ก็ยังคืนค่า `True` เสมอ ทำให้ฟังก์ชัน `_ensure_connection()` ไม่ยอมทำการ Reconnect ให้เพราะเข้าใจผิดว่ายังเชื่อมต่ออยู่

#### ค. ขาดกลไก Liveness Probe (Telnet Keepalive / Heartbeat)
Netmiko มีเมธอด `handler.is_alive()` ซึ่งสำหรับ Telnet จะส่งคำสั่งมาตรฐาน RFC 854 คือ `IAC + NOP` (`\xff\xf1`) ไปยัง Switch เพื่อทดสอบว่า Socket ยังตอบสนองหรือไม่ แต่ในระบบเดิมไม่ได้นำ `is_alive()` มาใช้ตรวจสอบสถานะการเชื่อมต่อ

#### ง. ฟังก์ชัน `send_interactive()` ขาด Exception Handling & Auto-Reconnect
ใน `send_command()` และ `send_config()` มีการตรวจจับ `closed`, `eof`, `connection reset` และทำการ Reconnect แต่ใน `send_interactive()` ซึ่งเป็นฟังก์ชันหลักที่หน้าต่าง CLI Terminal ใช้งานโดยตรง **ไม่มีการ Reconnect เลยแม้แต่บรรทัดเดียว**:
```python
# โค้ดเดิมใน send_interactive
except Exception as e:
    return {"success": False, "output": f"Error: {err_msg}", "prompt": ""}
```
เมื่อ Switch หลุด Socket จะพัง และ `self.pool` ยังเก็บ Socket พังนั้นไว้ คำสั่งถัดไปทั้งหมดจึงล้มเหลวอย่างต่อเนื่อง

#### จ. ปัญหา Authentication และ Mode บน Switch Telnet
บน Cisco Switch หลายตัว การตั้งค่า Telnet มักจะใช้ `line vty 0 4` + `login` + `password <pwd>` (ไม่มี Username)
หากส่ง Username ว่างหรือส่งผิดจังหวะ Netmiko Telnet Driver อาจเกิด timeout ระหว่าง handshaking และเมื่อเชื่อมต่อสำเร็จ Switch จะเริ่มต้นที่ User Mode (`Switch>`) หากไม่รัน `enable` หรือ `terminal length 0` ให้เรียบร้อย คำสั่งที่ส่งไปจะติด pagination `--More--` และหลุดการเชื่อมต่อ

---

## 3. แผนการแก้ไขเชิงระบบ (Architecture & Implementation Plan)

### 3.1 การแก้ไขใน `connection_manager.py`
1. **ปรับปรุง `is_connected()` ให้รองรับ Active Liveness Check**:
   - เพิ่มออปชัน `check_alive=True` โดยใช้ `handler.is_alive()` (ส่ง Telnet IAC NOP) ตรวจสอบสถานะจริงของ Socket
   - หากพบว่า Socket ตาย ให้ทำการลบออกจาก `self.pool` อัตโนมัติทันที
2. **ปรับปรุง `_ensure_connection()`**:
   - หากพบว่า session ไม่อยู่ในสภาพพร้อมใช้งาน (not alive) ให้สั่ง `connect()` ใหม่ทันทีแบบโปร่งใส (Transparent Auto-Reconnect)
3. **ยกเครื่อง `send_interactive()` สำหรับ CLI Terminal**:
   - เพิ่มกลไก Auto-Reconnect เมื่อพบข้อผิดพลาดด้าน Socket (`closed`, `eof`, `reset`, `broken pipe`, `timeout`)
   - ล้าง Buffer ตกค้าง (`clear_buffer()`) ก่อนส่งคำสั่งเสมอ
   - ปรับระยะเวลา `read_channel_timing(last_read=1.5, read_timeout=15.0)` ให้เหมาะสมกับอุปกรณ์จริง
   - ปรับปรุงการสกัด Prompt จริงจาก Switch/Router เช่น `S1#`, `S1(config)#`, `S1(config-if)#` ให้แม่นยำ 100%
4. **เสริมสร้าง Telnet Connection Parameters สำหรับ Switch**:
   - เมื่อเชื่อมต่อสำเร็จ สั่ง `terminal length 0` และ `terminal width 512` เสมอ
   - รองรับทั้ง Password-only authentication และ Username/Password
   - มีฟังก์ชัน Keepalive/Heartbeat สำหรับส่งสัญญาณ NOP ป้องกัน Switch ตัดการเชื่อมต่อ

### 3.2 การแก้ไขใน `app.py`
1. ปรับปรุง `/api/cli/execute` ให้ส่งคำสั่งและรับผลลัพธ์จากอุปกรณ์จริงเสมอ
2. เมื่ออุปกรณ์ออฟไลน์จริง ให้แจ้งเตือนสถานะชัดเจนว่าอุปกรณ์ไม่ได้เชื่อมต่อ พร้อมแนะนำการเชื่อมต่อ แทนการส่งข้อความจำลอง
3. ส่งทั้ง Output จริงและ Prompt จริงกลับไปที่หน้าบ้าน เพื่อให้ Frontend อัปเดต Prompt ตามโหมดปัจจุบันของอุปกรณ์ได้อย่างถูกต้อง

### 3.3 การแก้ไขใน `static/js/app.js`
1. เพิ่มฟังก์ชัน `appendConsole(text, cssClass)` ให้สมบูรณ์ เพื่อรองรับการพิมพ์ผลลัพธ์จาก GUI ทุกคำสั่งลงหน้าต่าง Console
2. ปรับปรุง `sendConsoleCmd()` ให้แสดง Output และสลับ Prompt ตามที่อุปกรณ์ตอบกลับมาจริง
3. ปรับปรุง `refreshDeviceCliPrompt()` ให้ดึง Prompt สดจากอุปกรณ์ทุกครั้งที่เปิดแท็บ CLI หรือสลับอุปกรณ์

---

## 4. แผนการทดสอบ (Tester Suite Specification)

สร้างไฟล์ทดสอบ `tests/test_cli_and_telnet_switch.py` เพื่อพิสูจน์การทำงาน:
- **Test Case 1 (CLI Live Execution)**: ทดสอบว่าคำสั่งผ่าน `/api/cli/execute` เรียกใช้ session จริง ไม่คืนค่า mock
- **Test Case 2 (Interactive Real Prompt Extraction)**: ทดสอบการสกัด prompt จริงจาก Router และ Switch
- **Test Case 3 (Telnet Socket Liveness Detection)**: ทดสอบว่า `is_connected()` ตรวจจับ socket ปิดได้ถูกต้อง
- **Test Case 4 (Telnet Connection Drop & Auto-Reconnect)**: จำลองการหลุดของ socket บน Switch แล้วทดสอบว่าระบบ reconnect อัตโนมัติและทำงานต่อได้โดยไม่ต้องรีสตาร์ท
- **Test Case 5 (Switch Telnet Options & Pagination)**: ตรวจสอบการส่ง `terminal length 0` และ `terminal width 512`
- **Test Case 6 (appendConsole Frontend Verification)**: ตรวจสอบความถูกต้องของ JavaScript Console binding ใน app.js
