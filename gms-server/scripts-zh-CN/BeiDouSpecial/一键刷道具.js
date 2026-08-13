/**北斗刷道具



---By hanmburger*/
var status;

//Start
function start()
{
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection)
{
    if (CheckStatus(mode))
    {
        if (status == 0)
        {
            //第一层对话
            cm.sendGetNumber("请输入要生成的物品 ID",0,0,99999999);
        }
        else if (status == 1)
        {
            //第二层对话
            if (cm.canGenerateItem(selection))
            {
                var item = cm.gainItem(selection,1);
                if (item == null)
                {
                    cm.sendOk("物品 ID " + selection + " 生成失败，请检查对应背包是否已满。");
                }
                else
                {
                    var text = "生成成功：#i" + selection + "# #t" + selection + "# (" + selection + ")";
                    cm.sendOk(text);
                }
                cm.dispose();
            }
            else
            {
                if (!cm.itemExists(selection))
                {
                    cm.sendOk("物品 ID " + selection + " 不存在，请检查输入是否正确。");
                }
                else if (!cm.hasItemData(selection))
                {
                    cm.sendOk("物品 ID " + selection + " 缺少完整的服务端数据，已取消生成。");
                }
                else
                {
                    cm.sendOk("物品 ID " + selection + " 无法安全生成，已取消操作。");
                }
                cm.dispose();
            }
        }
        else
        {
            //最后一层对话完继续循环至此，退出结束
            cm.dispose();
        }
    }
}

function CheckStatus(mode)
{
    if (mode == -1)
    {
        cm.dispose();//点击了取消，停止，结束
        return false;
    }

    if (mode == 1)
    {
        status++;
    }
    else
    {
        status--;
    }

    if (status == -1)
    {
        cm.dispose();//防止第一层对话带有上一项或者取消按钮而产生bug。
        return false;
    }
    return true;
}
