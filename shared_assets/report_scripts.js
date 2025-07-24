function toggleInstances(groupIndex) {
    const container = document.getElementById('instances-' + groupIndex);
    const icon = document.getElementById('toggle-' + groupIndex);
    
    if (container.classList.contains('expanded')) {
        container.classList.remove('expanded');
        icon.classList.remove('expanded');
    } else {
        container.classList.add('expanded');
        icon.classList.add('expanded');
    }
}

function toggleRulesList() {
    const rulesList = document.getElementById('rules-list');
    rulesList.classList.toggle('show');
}

function jumpToRule(groupIndex) {
    // 关闭规则列表
    toggleRulesList();
    
    // 滚动到对应的规则组
    const ruleGroup = document.querySelector(`[data-group-index="${groupIndex}"]`);
    if (ruleGroup) {
        ruleGroup.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        // 自动展开该规则组
        const container = document.getElementById('instances-' + groupIndex);
        const icon = document.getElementById('toggle-' + groupIndex);
        if (container && !container.classList.contains('expanded')) {
            container.classList.add('expanded');
            icon.classList.add('expanded');
        }
        
        // 添加高亮效果
        ruleGroup.style.boxShadow = '0 0 20px rgba(233, 30, 99, 0.3)';
        setTimeout(() => {
            ruleGroup.style.boxShadow = '';
        }, 2000);
    }
}

// 返回顶部按钮功能
function initBackToTopButton() {
    const backToTopBtn = document.getElementById('back-to-top');
    if (!backToTopBtn) return;
    
    // 监听滚动事件
    window.addEventListener('scroll', function() {
        if (window.pageYOffset > 300) {
            backToTopBtn.classList.add('show');
        } else {
            backToTopBtn.classList.remove('show');
        }
    });
    
    // 点击返回顶部
    backToTopBtn.addEventListener('click', function() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
}

// 点击模态框背景关闭
document.addEventListener('DOMContentLoaded', function() {
    const rulesListContainer = document.getElementById('rules-list');
    if (rulesListContainer) {
        rulesListContainer.addEventListener('click', function(e) {
            if (e.target === rulesListContainer) {
                toggleRulesList();
            }
        });
    }
    
    // ESC 键关闭模态框
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const rulesList = document.getElementById('rules-list');
            if (rulesList && rulesList.classList.contains('show')) {
                toggleRulesList();
            }
        }
    });
    
    // 初始化返回顶部按钮
    initBackToTopButton();
});