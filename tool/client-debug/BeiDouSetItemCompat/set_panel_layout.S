.intel_syntax noprefix
.text
.global allocate_frame, collect_panel, save_slot, store_slot, save_widget, size_panel, select_slot, draw_column, position_panel
.extern _collect_slots
.global make_dark_layer, format_title

/* MakeLayer is thiscall/RET 28; only its final ARGB argument changes. */
make_dark_layer:
    push eax
    call dark_base
dark_base:
    pop eax
    sub eax, offset dark_base
    cmp ecx, [eax+0xa8ac]
    je dark_color
    add eax, 0x8880
    cmp ecx, eax
    je dark_color
    sub eax, 0x2020
    cmp ecx, eax
    jne dark_dispatch
dark_color:
    mov DWORD PTR [esp+32], 0xff1e1e1e
dark_dispatch:
    call dark_target
dark_target:
    pop eax
    sub eax, offset dark_target
    mov eax, [eax+0xa894]
    xchg eax, [esp]
    ret

/* Avoid a duplicated suffix when an admin name already ends in set (UTF-16). */
format_title:
    push eax
    push edx
    push esi
    push ebx
    call title_base
title_base:
    pop ebx
    sub ebx, offset title_base
    lea edx, [ebx+0x312f00]
    mov esi, [esp+28]
    mov eax, esi
title_end:
    cmp WORD PTR [esi], 0
    je title_suffix
    add esi, 2
    jmp title_end
title_suffix:
    sub esi, eax
    cmp esi, 4
    jb title_ready
    cmp DWORD PTR [eax+esi-4], 0x88c55957
    jne title_ready
    lea edx, [ebx+0x5576]
title_ready:
    mov [esp+24], edx
    pop ebx
    pop esi
    pop edx
    pop eax
    ret

/* All image references are base-relative. No new HIGHLOW operands. */
allocate_frame:
    pop eax
    sub esp, 0x1000
    test DWORD PTR [esp], eax
    sub esp, 0x400
    jmp eax

collect_panel:
    pushad
    call collect_base
collect_base:
    pop ebx
    sub ebx, offset collect_base
    lea eax, [ebx+0x1b7f]
    call eax
    lea eax, [ebp-0x1000]
    push eax
    push DWORD PTR [ebp-0x3b0]
    push edi
    push ebx
    call _collect_slots
    add esp, 16
    mov [ebp-0x1010], eax
    popad
    ret

save_slot:
    mov [ebp-0x184], eax
    cmp DWORD PTR [ebp-0x164], 9
    ret

store_slot:
    pop eax
    sub esp, 12
    push eax
    push edx
    mov edx, [ebp-0x184]
    mov WORD PTR [ebx+0xf6], dx
    inc DWORD PTR [esi+0x6c]
    pop edx
    ret

save_widget:
    mov eax, [ebp-0x3b4]
    mov [ebp-0x1014], eax
    ret

size_panel:
    push ebx
    push edx
    push esi
    call size_base
size_base:
    pop ebx
    sub ebx, offset size_base
    shl eax, 4
    add eax, 28
    mov esi, eax
    sub eax, 29
    xor edx, edx
    mov ecx, 448
    div ecx
    inc eax
    imul eax, eax, 236
    mov [ebx+0x888c], eax
    mov eax, esi
    cmp eax, 476
    jle size_done
    mov eax, 476
size_done:
    lea ecx, [ebx+0x8880]
    pop esi
    pop edx
    pop ebx
    ret

select_slot:
    mov ebx, [ebp+eax*4-0x1000]
    push edx
    call select_base
select_base:
    pop edx
    sub edx, offset select_base
    lea edx, [edx+0x327b]
    xchg edx, [esp]
    ret

draw_column:
    push eax
    push edx
    push ebx
    mov eax, [esp+16]
    sub eax, 7
    xor edx, edx
    mov ebx, 448
    div ebx
    imul eax, eax, 236
    add ecx, eax
    add edx, 7
    mov [esp+16], edx
    pop ebx
    pop edx
    pop eax
    push ebx
    call draw_base
draw_base:
    pop ebx
    sub ebx, offset draw_base
    lea ebx, [ebx+0x174d]
    xchg ebx, [esp]
    ret

/* Keep the primary tooltip and its continuation adjacent inside 800x600.
   Native Create at EXE 0x8f32c6..0x8f32ed proves this viewport contract. */
position_panel:
    pushad
    call position_base
position_base:
    pop ebx
    sub ebx, offset position_base
    mov edi, [ebp-0x1014]
    mov esi, [edi+0xc]
    mov ecx, [ebp+0xc]
    mov eax, 799
    sub eax, esi
    sub eax, 4
    sub eax, [ebx+0x888c]
    cmp ecx, eax
    cmovg ecx, eax
    xor eax, eax
    test ecx, ecx
    cmovs ecx, eax
    mov [ebp-0x1018], ecx
    mov eax, [edi+8]
    cmp eax, [ebx+0x8888]
    cmovl eax, [ebx+0x8888]
    mov edx, 599
    sub edx, eax
    mov eax, [esp+36]
    cmp eax, edx
    cmovg eax, edx
    xor edx, edx
    test eax, eax
    cmovs eax, edx
    cmp BYTE PTR [ebx+0x6854], 0
    je position_y_done
    cmp eax, [ebx+0x6868]
    cmovl eax, [ebx+0x6868]
position_y_done:
    mov [ebp-0x101c], eax
    mov edx, ecx
    mov ecx, eax
    mov eax, [edi+0x10]
    lea edi, [ebx+0x1b07]
    call edi
    cmp BYTE PTR [ebx+0x6854], 0
    je position_set
    mov eax, [ebx+0x6870]
    test eax, eax
    je position_set
    mov edx, [ebp-0x1018]
    mov ecx, [ebp-0x101c]
    sub ecx, [ebx+0x6868]
    call edi
position_set:
    mov ecx, [ebp-0x1018]
    lea ecx, [ecx+esi+4]
    push DWORD PTR [ebp-0x101c]
    mov eax, [ebp-0x3cc]
    mov edx, [ebx+0x8890]
    lea edi, [ebx+0x2a75]
    call edi
    add esp, 4
    popad
    ret
