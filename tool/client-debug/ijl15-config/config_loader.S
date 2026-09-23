.intel_syntax noprefix
.code32
.section .text
.global config_loader_entry

.equ IAT_STRTOL, 0x2014c
.equ IAT_FCLOSE, 0x20198
.equ IAT_FGETS, 0x2019c
.equ IAT_FOPEN_S, 0x20190
.equ STRING_ASSIGN_RANGE, 0x123c0
.equ STRING_DESTRUCTOR, 0x137e0
.equ STRING_MOVE_ASSIGN, 0x13aa0
.equ SERVER_PORT, 0x36594
.equ SERVER_ADDRESS, 0x3659c
.equ LOCAL_SIZE, 0x230
.equ LINE_BUFFER, 0x004
.equ KEY_POINTER, 0x204
.equ VALUE_POINTER, 0x208
.equ VALUE_LENGTH, 0x20c
.equ TEMP_STRING, 0x210

config_loader_entry:
    pushfd
    pushad
    call .Lentry_address
.Lentry_address:
    pop ebp
    sub ebp, .Lentry_address - config_loader_entry
    mov ebx, ebp
    sub ebx, 0xb16b00b5

    sub esp, LOCAL_SIZE
    mov edi, esp
    mov dword ptr [edi], 0

    lea eax, [edi]
    lea ecx, [ebp + .Lconfig_name - config_loader_entry]
    lea edx, [ebp + .Lread_mode - config_loader_entry]
    push edx
    push ecx
    push eax
    call dword ptr [ebx + IAT_FOPEN_S]
    add esp, 12
    test eax, eax
    jne .Ldone
    cmp dword ptr [edi], 0
    je .Ldone

.Lread_line:
    push dword ptr [edi]
    push 0x200
    lea eax, [edi + LINE_BUFFER]
    push eax
    call dword ptr [ebx + IAT_FGETS]
    add esp, 12
    test eax, eax
    je .Lclose

    lea esi, [edi + LINE_BUFFER]
.Lskip_key_space:
    mov al, byte ptr [esi]
    cmp al, ' '
    je .Ladvance_key
    cmp al, 9
    jne .Lcheck_line_start
.Ladvance_key:
    inc esi
    jmp .Lskip_key_space

.Lcheck_line_start:
    test al, al
    je .Lread_line
    cmp al, ';'
    je .Lread_line
    cmp al, '#'
    je .Lread_line
    cmp al, '['
    je .Lread_line
    cmp al, 13
    je .Lread_line
    cmp al, 10
    je .Lread_line
    mov dword ptr [edi + KEY_POINTER], esi
    mov ecx, esi

.Lfind_separator:
    mov al, byte ptr [ecx]
    test al, al
    je .Lread_line
    cmp al, 13
    je .Lread_line
    cmp al, 10
    je .Lread_line
    cmp al, '='
    je .Lseparator_found
    cmp al, ':'
    je .Lseparator_found
    inc ecx
    jmp .Lfind_separator

.Lseparator_found:
    mov byte ptr [ecx], 0
    mov edx, ecx
.Ltrim_key_end:
    cmp edx, dword ptr [edi + KEY_POINTER]
    jbe .Lkey_trimmed
    mov al, byte ptr [edx - 1]
    cmp al, ' '
    je .Ldrop_key_byte
    cmp al, 9
    jne .Lkey_trimmed
.Ldrop_key_byte:
    dec edx
    mov byte ptr [edx], 0
    jmp .Ltrim_key_end

.Lkey_trimmed:
    inc ecx
.Lskip_value_space:
    mov al, byte ptr [ecx]
    cmp al, ' '
    je .Ladvance_value
    cmp al, 9
    jne .Lvalue_start
.Ladvance_value:
    inc ecx
    jmp .Lskip_value_space

.Lvalue_start:
    mov dword ptr [edi + VALUE_POINTER], ecx
    mov edx, ecx
.Lfind_value_end:
    mov al, byte ptr [edx]
    test al, al
    je .Ltrim_value_end
    cmp al, 13
    je .Lterminate_value
    cmp al, 10
    je .Lterminate_value
    cmp al, ';'
    je .Lterminate_value
    cmp al, '#'
    je .Lterminate_value
    inc edx
    jmp .Lfind_value_end
.Lterminate_value:
    mov byte ptr [edx], 0

.Ltrim_value_end:
    cmp edx, dword ptr [edi + VALUE_POINTER]
    jbe .Lvalue_trimmed
    mov al, byte ptr [edx - 1]
    cmp al, ' '
    je .Ldrop_value_byte
    cmp al, 9
    jne .Lvalue_trimmed
.Ldrop_value_byte:
    dec edx
    mov byte ptr [edx], 0
    jmp .Ltrim_value_end

.Lvalue_trimmed:
    sub edx, dword ptr [edi + VALUE_POINTER]
    mov dword ptr [edi + VALUE_LENGTH], edx

    mov esi, dword ptr [edi + KEY_POINTER]
    lea edx, [ebp + .Laddress_key - config_loader_entry]
    call .Lkey_equals_ignore_case
    test eax, eax
    je .Lcheck_port_key

    mov edx, dword ptr [edi + VALUE_LENGTH]
    test edx, edx
    je .Lread_line
    cmp edx, 63
    ja .Lread_line
    lea ecx, [edi + TEMP_STRING]
    xor eax, eax
    mov dword ptr [ecx], eax
    mov dword ptr [ecx + 4], eax
    mov dword ptr [ecx + 8], eax
    mov dword ptr [ecx + 12], eax
    mov dword ptr [ecx + 16], eax
    mov dword ptr [ecx + 20], 15
    push edx
    push dword ptr [edi + VALUE_POINTER]
    lea eax, [ebx + STRING_ASSIGN_RANGE]
    call eax
    lea eax, [edi + TEMP_STRING]
    push eax
    lea ecx, [ebx + SERVER_ADDRESS]
    lea eax, [ebx + STRING_MOVE_ASSIGN]
    call eax
    lea ecx, [edi + TEMP_STRING]
    lea eax, [ebx + STRING_DESTRUCTOR]
    call eax
    jmp .Lread_line

.Lcheck_port_key:
    mov esi, dword ptr [edi + KEY_POINTER]
    lea edx, [ebp + .Lport_key - config_loader_entry]
    call .Lkey_equals_ignore_case
    test eax, eax
    je .Lread_line
    cmp dword ptr [edi + VALUE_LENGTH], 0
    je .Lread_line
    push 10
    push 0
    push dword ptr [edi + VALUE_POINTER]
    call dword ptr [ebx + IAT_STRTOL]
    add esp, 12
    cmp eax, 1
    jl .Lread_line
    cmp eax, 65535
    jg .Lread_line
    mov dword ptr [ebx + SERVER_PORT], eax
    jmp .Lread_line

.Lclose:
    push dword ptr [edi]
    call dword ptr [ebx + IAT_FCLOSE]
    add esp, 4

.Ldone:
    add esp, LOCAL_SIZE
    popad
    popfd

    # Reproduce the seven bytes replaced by the initialization trampoline.
    push esi
    sub esp, 0x18
    mov dword ptr [ebp - 0x30], esp
    .byte 0xe9
    .long 0xbadc0ffe

.Lkey_equals_ignore_case:
    push esi
    push edi
    mov edi, edx
.Lcompare_key_byte:
    mov al, byte ptr [esi]
    cmp al, 'A'
    jb .Lkey_byte_ready
    cmp al, 'Z'
    ja .Lkey_byte_ready
    add al, 'a' - 'A'
.Lkey_byte_ready:
    cmp al, byte ptr [edi]
    jne .Lkey_not_equal
    test al, al
    je .Lkey_equal
    inc esi
    inc edi
    jmp .Lcompare_key_byte
.Lkey_not_equal:
    xor eax, eax
    pop edi
    pop esi
    ret
.Lkey_equal:
    mov eax, 1
    pop edi
    pop esi
    ret

.Lconfig_name:
    .asciz "config.ini"
.Lread_mode:
    .asciz "r"
.Laddress_key:
    .asciz "serverip_address"
.Lport_key:
    .asciz "serverip_port"

