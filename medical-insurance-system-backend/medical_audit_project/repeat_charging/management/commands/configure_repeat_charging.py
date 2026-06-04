"""
重复收费检测配置管理命令
Django Management Command for Repeat Charging Configuration
"""

from django.core.management.base import BaseCommand, CommandError
from repeat_charging.integration import configure_ai_analysis, get_detection_config, get_module_status


class Command(BaseCommand):
    help = '配置重复收费检测模块'

    def add_arguments(self, parser):
        parser.add_argument(
            '--enable-ai',
            action='store_true',
            help='启用AI分析功能'
        )
        
        parser.add_argument(
            '--api-key',
            type=str,
            help='DeepSeek API密钥'
        )
        
        parser.add_argument(
            '--base-url',
            type=str,
            default='https://api.deepseek.com',
            help='DeepSeek API基础URL'
        )
        
        parser.add_argument(
            '--status',
            action='store_true',
            help='显示模块状态'
        )
        
        parser.add_argument(
            '--config',
            action='store_true',
            help='显示当前配置'
        )

    def handle(self, *args, **options):
        if options['status']:
            self.show_status()
        elif options['config']:
            self.show_config()
        elif options['enable_ai']:
            self.configure_ai(options)
        else:
            self.stdout.write(
                self.style.WARNING('请指定操作: --status, --config, 或 --enable-ai')
            )

    def show_status(self):
        """显示模块状态"""
        self.stdout.write(self.style.SUCCESS('重复收费检测模块状态:'))
        
        try:
            status = get_module_status()
            
            self.stdout.write(f"  模块版本: {status.get('module_version', 'unknown')}")
            self.stdout.write(f"  基础检测: {'✓' if status.get('basic_detection_available') else '✗'}")
            self.stdout.write(f"  组套检测: {'✓' if status.get('package_detection_available') else '✗'}")
            self.stdout.write(f"  AI分析: {'✓' if status.get('ai_analysis_available') else '✗'}")
            self.stdout.write(f"  AI客户端: {status.get('ai_client_status', 'unknown')}")
            
            dependencies = status.get('dependencies', {})
            self.stdout.write("\n  依赖状态:")
            for dep, available in dependencies.items():
                self.stdout.write(f"    {dep}: {'✓' if available else '✗'}")
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'获取状态失败: {e}')
            )

    def show_config(self):
        """显示当前配置"""
        self.stdout.write(self.style.SUCCESS('当前检测配置:'))
        
        try:
            config = get_detection_config()
            
            for key, value in config.items():
                self.stdout.write(f"  {key}: {value}")
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'获取配置失败: {e}')
            )

    def configure_ai(self, options):
        """配置AI分析功能"""
        api_key = options.get('api_key')
        base_url = options.get('base_url')
        
        if not api_key:
            raise CommandError('启用AI分析需要提供 --api-key 参数')
        
        self.stdout.write('正在配置AI分析功能...')
        
        try:
            success = configure_ai_analysis(api_key, base_url)
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS('AI分析功能配置成功!')
                )
                self.stdout.write(f'API密钥: {api_key[:8]}...')
                self.stdout.write(f'基础URL: {base_url}')
            else:
                self.stdout.write(
                    self.style.ERROR('AI分析功能配置失败')
                )
                
        except Exception as e:
            raise CommandError(f'配置AI分析功能时出错: {e}')