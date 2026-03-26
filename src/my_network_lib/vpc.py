from dataclasses import dataclass
from typing import Optional, List
import pulumi
import pulumi_aws as aws
import ipaddress

@dataclass
class MyVpcArgs:
    cidr_block: str
    enable_dns_hostname: bool = True
    create_private_subnets: bool = True
    create_public_subnets: bool = False  
    tags: pulumi.Input[dict] = None

class MyVpc(pulumi.ComponentResource):
    def __init__(self, name: str, args: MyVpcArgs, opts: pulumi.ResourceOptions = None):
        super().__init__('custom:resource:MyVpc', name, {}, opts)
        
        # 1. Fetch available AZs in the current region
        # We filter for 'available' and 'opt-in-not-required' to avoid local zones if not wanted
        azs = aws.get_availability_zones(state="available")

        self.vpc = aws.ec2.Vpc(f"{name}-vpc",
            cidr_block=args.cidr_block,
            enable_dns_hostnames=args.enable_dns_hostname,
            tags=args.tags,
            opts=pulumi.ResourceOptions(parent=self)
        )

        # 2. Automatically calculate smaller CIDR blocks
        network = ipaddress.ip_network(args.cidr_block)
        cidr_iterator = network.subnets(new_prefix=network.prefixlen + 3)

        # 3. Create Public Subnets across all AZs
        self.public_subnets = []
        if args.create_public_subnets:
            for i, az_name in enumerate(azs.names):
                public_subnet = aws.ec2.Subnet(f"{name}-public-sn-{i}",
                    vpc_id=self.vpc.id,
                    cidr_block=str(next(cidr_iterator)),
                    availability_zone=az_name,
                    map_public_ip_on_launch=True,
                    tags={**args.tags, "Name": f"{name}-public-{az_name}"} if args.tags else {"Name": f"{name}-public-{az_name}"},
                    opts=pulumi.ResourceOptions(parent=self.vpc)
                )
                self.public_subnets.append(public_subnet)

        # 4. Create Private Subnets across all AZs
        self.private_subnets = []
        if args.create_private_subnets:
            for i, az_name in enumerate(azs.names):
                private_subnet = aws.ec2.Subnet(f"{name}-private-sn-{i}",
                    vpc_id=self.vpc.id,
                    cidr_block=str(next(cidr_iterator)),
                    availability_zone=az_name,
                    tags={**args.tags, "Name": f"{name}-private-{az_name}"} if args.tags else {"Name": f"{name}-private-{az_name}"},
                    opts=pulumi.ResourceOptions(parent=self.vpc)
                )
                self.private_subnets.append(private_subnet)
        
        self.register_outputs({
            "vpc_id": self.vpc.id,
            "public_subnet_ids": [s.id for s in self.public_subnets],
            "private_subnet_ids": [s.id for s in self.private_subnets]
        })
